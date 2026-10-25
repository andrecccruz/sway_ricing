/*
 * bolhas: wallpaper animado para sway.
 *
 * Cria uma layer surface de fundo em cada monitor e desenha nela um
 * fragment shader GLSL (bolhas.frag) com tempo animado.
 *
 * - Limite de FPS (padrão 30). Só desenha quando o compositor pede um frame,
 *   então se o fundo estiver totalmente coberto a GPU fica parada.
 * - SIGUSR1 pausa/retoma, SIGHUP recarrega o shader do disco.
 *
 * Uso: bolhas [-f fps] [-d densidade] [-s shader.frag]
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <math.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include <EGL/egl.h>
#include <GLES2/gl2.h>
#include <wayland-client.h>
#include <wayland-egl.h>

#include "wlr-layer-shell-unstable-v1-client-protocol.h"

static const char *VERT_SRC =
	"attribute vec2 a;\n"
	"void main() { gl_Position = vec4(a, 0.0, 1.0); }\n";

struct output {
	struct wl_list link;
	struct wl_output *wl;
	uint32_t name;
	struct wl_surface *surface;
	struct zwlr_layer_surface_v1 *layer;
	struct wl_egl_window *ewin;
	EGLSurface esurf;
	struct wl_callback *frame_cb;
	int width, height;
	bool dirty;
};

static struct {
	struct wl_display *display;
	struct wl_compositor *compositor;
	struct zwlr_layer_shell_v1 *shell;
	struct wl_list outputs;

	EGLDisplay edpy;
	EGLConfig ecfg;
	EGLContext ectx;

	bool gl_ready, need_reload;
	GLuint prog, vbo;
	GLint u_res, u_time, u_dens;

	char shader_path[4096];
	double fps, density;
} st;

static volatile sig_atomic_t sig_quit, sig_pause, sig_reload;

static void on_signal(int sig)
{
	if (sig == SIGUSR1)
		sig_pause = 1;
	else if (sig == SIGHUP)
		sig_reload = 1;
	else
		sig_quit = 1;
}

static double now(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec + ts.tv_nsec / 1e9;
}

/* ---------- GL ---------- */

static char *read_file(const char *path)
{
	FILE *f = fopen(path, "rb");
	if (!f)
		return NULL;
	fseek(f, 0, SEEK_END);
	long len = ftell(f);
	fseek(f, 0, SEEK_SET);
	char *buf = malloc(len + 1);
	if (buf && fread(buf, 1, len, f) == (size_t)len) {
		buf[len] = '\0';
	} else {
		free(buf);
		buf = NULL;
	}
	fclose(f);
	return buf;
}

static GLuint compile(GLenum type, const char *src)
{
	GLuint s = glCreateShader(type);
	glShaderSource(s, 1, &src, NULL);
	glCompileShader(s);
	GLint ok;
	glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
	if (!ok) {
		char log[2048];
		glGetShaderInfoLog(s, sizeof(log), NULL, log);
		fprintf(stderr, "bolhas: erro ao compilar shader:\n%s\n", log);
		glDeleteShader(s);
		return 0;
	}
	return s;
}

/* Mantém o programa anterior se o novo shader não compilar. */
static void load_program(void)
{
	char *frag = read_file(st.shader_path);
	if (!frag) {
		fprintf(stderr, "bolhas: não consegui ler %s\n", st.shader_path);
		return;
	}
	GLuint vs = compile(GL_VERTEX_SHADER, VERT_SRC);
	GLuint fs = compile(GL_FRAGMENT_SHADER, frag);
	free(frag);
	if (!vs || !fs) {
		glDeleteShader(vs);
		glDeleteShader(fs);
		return;
	}

	GLuint p = glCreateProgram();
	glAttachShader(p, vs);
	glAttachShader(p, fs);
	glBindAttribLocation(p, 0, "a");
	glLinkProgram(p);
	glDeleteShader(vs);
	glDeleteShader(fs);
	GLint ok;
	glGetProgramiv(p, GL_LINK_STATUS, &ok);
	if (!ok) {
		char log[2048];
		glGetProgramInfoLog(p, sizeof(log), NULL, log);
		fprintf(stderr, "bolhas: erro ao linkar shader:\n%s\n", log);
		glDeleteProgram(p);
		return;
	}

	if (st.prog)
		glDeleteProgram(st.prog);
	st.prog = p;
	st.u_res = glGetUniformLocation(p, "u_res");
	st.u_time = glGetUniformLocation(p, "u_time");
	st.u_dens = glGetUniformLocation(p, "u_dens");
}

static void gl_init(void)
{
	/* Um triângulo que cobre a tela toda. */
	static const GLfloat verts[] = { -1, -1, 3, -1, -1, 3 };
	glGenBuffers(1, &st.vbo);
	glBindBuffer(GL_ARRAY_BUFFER, st.vbo);
	glBufferData(GL_ARRAY_BUFFER, sizeof(verts), verts, GL_STATIC_DRAW);
	load_program();
	st.gl_ready = true;
}

/* ---------- desenho ---------- */

static void frame_done(void *data, struct wl_callback *cb, uint32_t time)
{
	(void)time;
	struct output *o = data;
	wl_callback_destroy(cb);
	o->frame_cb = NULL;
}

static const struct wl_callback_listener frame_listener = {
	.done = frame_done,
};

static void draw(struct output *o, float t)
{
	eglMakeCurrent(st.edpy, o->esurf, o->esurf, st.ectx);
	if (!st.gl_ready)
		gl_init();
	if (st.need_reload) {
		st.need_reload = false;
		load_program();
	}

	glViewport(0, 0, o->width, o->height);
	if (st.prog) {
		glUseProgram(st.prog);
		glUniform2f(st.u_res, o->width, o->height);
		glUniform1f(st.u_time, t);
		glUniform1f(st.u_dens, st.density);
		glBindBuffer(GL_ARRAY_BUFFER, st.vbo);
		glEnableVertexAttribArray(0);
		glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, NULL);
		glDrawArrays(GL_TRIANGLES, 0, 3);
	} else {
		glClearColor(0.01f, 0.012f, 0.035f, 1.0f);
		glClear(GL_COLOR_BUFFER_BIT);
	}

	o->frame_cb = wl_surface_frame(o->surface);
	wl_callback_add_listener(o->frame_cb, &frame_listener, o);
	eglSwapBuffers(st.edpy, o->esurf);
	o->dirty = false;
}

/* ---------- layer surface por monitor ---------- */

static void output_destroy(struct output *o)
{
	if (o->frame_cb)
		wl_callback_destroy(o->frame_cb);
	if (o->esurf) {
		eglMakeCurrent(st.edpy, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
		eglDestroySurface(st.edpy, o->esurf);
	}
	if (o->ewin)
		wl_egl_window_destroy(o->ewin);
	if (o->layer)
		zwlr_layer_surface_v1_destroy(o->layer);
	if (o->surface)
		wl_surface_destroy(o->surface);
	wl_output_destroy(o->wl);
	wl_list_remove(&o->link);
	free(o);
}

static void layer_configure(void *data, struct zwlr_layer_surface_v1 *layer,
		uint32_t serial, uint32_t w, uint32_t h)
{
	struct output *o = data;
	zwlr_layer_surface_v1_ack_configure(layer, serial);
	if (w == 0 || h == 0)
		return;
	o->width = w;
	o->height = h;
	if (!o->ewin) {
		o->ewin = wl_egl_window_create(o->surface, w, h);
		o->esurf = eglCreateWindowSurface(st.edpy, st.ecfg,
				(EGLNativeWindowType)o->ewin, NULL);
		eglMakeCurrent(st.edpy, o->esurf, o->esurf, st.ectx);
		/* O ritmo vem dos frame callbacks, não do vsync do EGL. */
		eglSwapInterval(st.edpy, 0);
	} else {
		wl_egl_window_resize(o->ewin, w, h, 0, 0);
	}
	o->dirty = true;
}

static void layer_closed(void *data, struct zwlr_layer_surface_v1 *layer)
{
	(void)layer;
	output_destroy(data);
}

static const struct zwlr_layer_surface_v1_listener layer_listener = {
	.configure = layer_configure,
	.closed = layer_closed,
};

static void output_setup(struct output *o)
{
	o->surface = wl_compositor_create_surface(st.compositor);

	/* Região de input vazia: cliques passam direto. */
	struct wl_region *r = wl_compositor_create_region(st.compositor);
	wl_surface_set_input_region(o->surface, r);
	wl_region_destroy(r);

	o->layer = zwlr_layer_shell_v1_get_layer_surface(st.shell, o->surface,
			o->wl, ZWLR_LAYER_SHELL_V1_LAYER_BACKGROUND, "wallpaper");
	zwlr_layer_surface_v1_set_size(o->layer, 0, 0);
	zwlr_layer_surface_v1_set_anchor(o->layer,
			ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP |
			ZWLR_LAYER_SURFACE_V1_ANCHOR_BOTTOM |
			ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT |
			ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT);
	zwlr_layer_surface_v1_set_exclusive_zone(o->layer, -1);
	zwlr_layer_surface_v1_add_listener(o->layer, &layer_listener, o);
	wl_surface_commit(o->surface);
}

/* ---------- registry ---------- */

static void registry_global(void *data, struct wl_registry *reg, uint32_t name,
		const char *iface, uint32_t version)
{
	(void)data;
	(void)version;
	if (strcmp(iface, wl_compositor_interface.name) == 0) {
		st.compositor = wl_registry_bind(reg, name, &wl_compositor_interface, 1);
	} else if (strcmp(iface, zwlr_layer_shell_v1_interface.name) == 0) {
		st.shell = wl_registry_bind(reg, name, &zwlr_layer_shell_v1_interface, 1);
	} else if (strcmp(iface, wl_output_interface.name) == 0) {
		struct output *o = calloc(1, sizeof(*o));
		o->wl = wl_registry_bind(reg, name, &wl_output_interface, 1);
		o->name = name;
		wl_list_insert(&st.outputs, &o->link);
		if (st.compositor && st.shell)
			output_setup(o);
	}
}

static void registry_global_remove(void *data, struct wl_registry *reg, uint32_t name)
{
	(void)data;
	(void)reg;
	struct output *o, *tmp;
	wl_list_for_each_safe(o, tmp, &st.outputs, link) {
		if (o->name == name)
			output_destroy(o);
	}
}

static const struct wl_registry_listener registry_listener = {
	.global = registry_global,
	.global_remove = registry_global_remove,
};

/* ---------- main ---------- */

static bool egl_init(void)
{
	st.edpy = eglGetDisplay((EGLNativeDisplayType)st.display);
	if (st.edpy == EGL_NO_DISPLAY || !eglInitialize(st.edpy, NULL, NULL))
		return false;
	eglBindAPI(EGL_OPENGL_ES_API);

	static const EGLint cfg_attr[] = {
		EGL_SURFACE_TYPE, EGL_WINDOW_BIT,
		EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8,
		EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
		EGL_NONE,
	};
	EGLint n;
	if (!eglChooseConfig(st.edpy, cfg_attr, &st.ecfg, 1, &n) || n < 1)
		return false;

	static const EGLint ctx_attr[] = { EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE };
	st.ectx = eglCreateContext(st.edpy, st.ecfg, EGL_NO_CONTEXT, ctx_attr);
	return st.ectx != EGL_NO_CONTEXT;
}

static void usage(void)
{
	fprintf(stderr,
		"uso: bolhas [-f fps] [-d densidade] [-s shader.frag]\n"
		"  -f  limite de quadros por segundo (padrão 30)\n"
		"  -d  quantidade de partículas: 0.5 poucas, 1 normal, 1.5 muitas\n"
		"  -s  shader (padrão ~/.config/sway/bolhas/bolhas.frag)\n"
		"sinais: USR1 pausa/retoma, HUP recarrega o shader\n");
}

int main(int argc, char **argv)
{
	st.fps = 30;
	st.density = 1.0;
	const char *cfg = getenv("XDG_CONFIG_HOME");
	if (cfg && *cfg)
		snprintf(st.shader_path, sizeof(st.shader_path), "%s/sway/bolhas/bolhas.frag", cfg);
	else
		snprintf(st.shader_path, sizeof(st.shader_path), "%s/.config/sway/bolhas/bolhas.frag",
				getenv("HOME"));

	int opt;
	while ((opt = getopt(argc, argv, "f:d:s:h")) != -1) {
		switch (opt) {
		case 'f': st.fps = atof(optarg); break;
		case 'd': st.density = atof(optarg); break;
		case 's': snprintf(st.shader_path, sizeof(st.shader_path), "%s", optarg); break;
		default: usage(); return opt == 'h' ? 0 : 1;
		}
	}
	if (st.fps <= 0)
		st.fps = 30;

	struct sigaction sa = { .sa_handler = on_signal };
	sigemptyset(&sa.sa_mask);
	sigaction(SIGINT, &sa, NULL);
	sigaction(SIGTERM, &sa, NULL);
	sigaction(SIGUSR1, &sa, NULL);
	sigaction(SIGHUP, &sa, NULL);

	wl_list_init(&st.outputs);
	st.display = wl_display_connect(NULL);
	if (!st.display) {
		fprintf(stderr, "bolhas: sem conexão com o Wayland\n");
		return 1;
	}
	if (!egl_init()) {
		fprintf(stderr, "bolhas: falha ao iniciar EGL\n");
		return 1;
	}

	struct wl_registry *reg = wl_display_get_registry(st.display);
	wl_registry_add_listener(reg, &registry_listener, NULL);
	wl_display_roundtrip(st.display);
	if (!st.compositor || !st.shell) {
		fprintf(stderr, "bolhas: o compositor não suporta wlr-layer-shell\n");
		return 1;
	}
	struct output *o;
	wl_list_for_each(o, &st.outputs, link) {
		if (!o->surface)
			output_setup(o);
	}

	const double period = 1.0 / st.fps;
	const double start = now();
	double paused_at = 0, paused_total = 0, next = 0;
	bool paused = false;

	while (!sig_quit) {
		if (sig_pause) {
			sig_pause = 0;
			paused = !paused;
			if (paused)
				paused_at = now();
			else
				paused_total += now() - paused_at;
		}
		if (sig_reload) {
			sig_reload = 0;
			st.need_reload = true;
			wl_list_for_each(o, &st.outputs, link)
				o->dirty = true;
		}

		/* Desenha os monitores que já liberaram o frame anterior. */
		double n = now();
		double t = (paused ? paused_at : n) - start - paused_total;
		bool tick = !paused && n >= next;
		bool waiting = false;
		wl_list_for_each(o, &st.outputs, link) {
			if (!o->esurf || o->frame_cb)
				continue;
			if (tick || o->dirty)
				draw(o, (float)fmod(t, 3600.0));
			else if (!paused)
				waiting = true;
		}
		if (tick)
			next = n + period;

		int timeout = -1;
		if (waiting) {
			double d = next - now();
			timeout = d <= 0 ? 0 : (int)(d * 1000.0) + 1;
		}

		while (wl_display_prepare_read(st.display) != 0)
			wl_display_dispatch_pending(st.display);
		if (wl_display_flush(st.display) < 0 && errno != EAGAIN) {
			wl_display_cancel_read(st.display);
			break;
		}
		struct pollfd pfd = { .fd = wl_display_get_fd(st.display), .events = POLLIN };
		int r = poll(&pfd, 1, timeout);
		if (r > 0) {
			if (wl_display_read_events(st.display) < 0)
				break;
		} else {
			wl_display_cancel_read(st.display);
			if (r < 0 && errno != EINTR)
				break;
		}
		if (wl_display_dispatch_pending(st.display) < 0)
			break;
		if (r > 0 && (pfd.revents & (POLLERR | POLLHUP)))
			break;
	}

	struct output *tmp;
	wl_list_for_each_safe(o, tmp, &st.outputs, link)
		output_destroy(o);
	eglTerminate(st.edpy);
	wl_display_disconnect(st.display);
	return 0;
}
