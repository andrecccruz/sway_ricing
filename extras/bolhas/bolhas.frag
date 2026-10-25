// Wallpaper estilo PlayStation: fundo escuro azul/roxo, raios de luz,
// duas fitas de onda, bolhas douradas/brancas e estrelas em sobrevoo.
// Edite e aperte Win+Shift+r para recarregar sem reiniciar.
precision highp float;

uniform vec2 u_res;
uniform float u_time;
uniform float u_dens;   // 0.5 poucas, 1.0 normal, 1.5 muitas

vec3 hash32(vec2 p)
{
    vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
    p3 += dot(p3, p3.yxz + 33.33);
    return fract((p3.xxy + p3.yzz) * p3.zyx);
}

float hash12(vec2 p)
{
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

// Coordenadas: p.y de 0 (baixo) a 1 (topo), p.x de 0 a aspect.

vec3 background(vec2 p, float aspect)
{
    vec3 col = mix(vec3(0.008, 0.010, 0.030), vec3(0.030, 0.018, 0.065), p.y);
    vec2 c = p - vec2(aspect * 0.55, 0.42);
    col += vec3(0.020, 0.040, 0.095) * exp(-dot(c, c) * 2.5);
    vec2 r = p - vec2(aspect * 0.95, 0.05);
    col += vec3(0.040, 0.015, 0.060) * exp(-dot(r, r) * 3.0);
    return col;
}

// Raios de luz suaves vindos do canto superior esquerdo, balançando devagar.
float ray(vec2 d, float center, float width)
{
    float x = (atan(d.y, d.x) - center) / width;
    return exp(-x * x);
}

vec3 lightRays(vec2 p, float t)
{
    vec2 d = p - vec2(-0.15, 1.20);
    float fall = exp(-length(d) * 1.1);
    float r1 = ray(d, -0.50 + 0.05 * sin(t * 0.11), 0.06);
    float r2 = ray(d, -0.78 + 0.04 * sin(t * 0.15 + 1.7), 0.04);
    return vec3(0.55, 0.62, 0.90) * (r1 * 0.35 + r2 * 0.25) * fall;
}

// Linha fina com um leve brilho em volta.
float thinLine(float dy, float px)
{
    return 1.0 - smoothstep(0.0, 1.6 * px, abs(dy)) + 0.10 * exp(-abs(dy) * 90.0);
}

// Fita de onda translúcida com bordas claras.
vec3 ribbon(vec2 p, float t, float base, float spd, float ph, vec3 tint, float px)
{
    float x = p.x;
    float c = base + 0.045 * sin(x * 2.1 + t * spd + ph)
                   + 0.025 * sin(x * 4.3 - t * spd * 1.6 + ph * 2.0);
    float th = 0.030 + 0.022 * sin(x * 1.4 - t * spd * 0.7 + ph * 3.0);
    float top = c + th;
    float bot = c - th;
    float inside = smoothstep(-px, px, p.y - bot) * smoothstep(-px, px, top - p.y);
    float shade = mix(0.35, 1.0, clamp((p.y - bot) / (top - bot), 0.0, 1.0));
    float fade = 0.55 + 0.45 * sin(x * 1.1 + t * spd * 0.5 + ph);
    float a = inside * shade * 0.07
            + thinLine(p.y - top, px) * 0.45
            + thinLine(p.y - bot, px) * 0.25;
    return tint * a * fade;
}

// Uma camada de bolhas. k = 0: perto (grandes, desfocadas, rápidas);
// k = 1: longe (pequenas, nítidas, lentas). Cada célula da grade tem no
// máximo uma bolha, que nasce, flutua e some; ao renascer muda de lugar.
vec3 bubbleLayer(vec2 p, float t, float i, float px)
{
    float k = i / 3.0;
    float cs = mix(0.20, 0.045, k);
    float spd = mix(0.030, 0.010, k);
    vec2 g = vec2(p.x + t * spd, p.y) / cs;
    vec2 id = floor(g);
    vec2 f = fract(g) - 0.5;

    vec3 h = hash32(id + i * 31.7);
    float ph = t * (0.04 + 0.06 * h.y) + h.z;
    float cyc = floor(ph);
    float life = fract(ph);
    vec3 h2 = hash32(id * 1.37 + cyc * 7.13 + i * 3.1 + 11.0);
    vec3 h3 = hash32(id * 2.11 + cyc * 3.71 + i * 5.3 + 47.0);

    // Concentradas numa faixa no meio da tela.
    float cy = (id.y + 0.5) * cs;
    float band = exp(-pow((cy - 0.50) / 0.16, 2.0));
    if (h2.x > band * mix(0.22, 0.15, k) * u_dens)
        return vec3(0.0);

    float r = mix(0.18, 0.38, h2.y);
    vec2 c = (h3.xy * 2.0 - 1.0) * (0.44 - r);
    c.y += 0.04 * sin(t * 0.6 + h3.z * 6.2832);
    vec2 q = f - c;
    float d = length(q);

    float blur = mix(0.55, 0.15, k) * r + 1.5 * px / cs;
    float disk = 1.0 - smoothstep(r - blur, r, d);
    // Esfera: miolo transparente, borda mais clara e um brilho no alto à esquerda.
    float body = disk * (0.25 + 0.75 * pow(clamp(d / r, 0.0, 1.0), 2.5));
    float spec = (1.0 - smoothstep(0.0, 0.30 * r, length(q - vec2(-0.35, 0.35) * r))) * disk * 0.8;

    float alpha = smoothstep(0.0, 0.25, life) * (1.0 - smoothstep(0.65, 1.0, life));
    vec3 col = h2.z < 0.55 ? vec3(1.0, 0.78, 0.45) : vec3(0.85, 0.90, 1.0);
    return col * (body + spec) * alpha * mix(0.35, 0.80, k);
}

// Estrelas pequenas atravessando da direita para a esquerda, crescendo um pouco.
vec3 stars(vec2 p, float aspect, float t, float px)
{
    float cs = 0.05;
    float spd = 0.07;
    vec2 g = vec2(p.x + t * spd, p.y) / cs;
    vec2 id = floor(g);
    vec2 f = fract(g) - 0.5;
    vec3 h = hash32(id + 91.3);
    if (h.x > 0.035 * u_dens)
        return vec3(0.0);

    vec2 c = (h.yz - 0.5) * 0.6;
    float sx = (id.x + 0.5 + c.x) * cs - t * spd;
    float grow = mix(1.8, 0.6, clamp(sx / aspect, 0.0, 1.0));
    float r = (1.0 + 1.5 * h.y) * px * grow;
    float dc = length(f - c);   // em unidades de célula
    float d = dc * cs;
    float core = 1.0 - smoothstep(0.0, r, d);
    // O brilho precisa zerar antes da borda da célula, senão aparecem quadrados.
    float glow = exp(-d / (r * 2.5)) * 0.35 * (1.0 - smoothstep(0.08, 0.19, dc));
    float tw = 0.65 + 0.35 * sin(t * (2.0 + 3.0 * h.z) + h.y * 30.0);
    return vec3(0.85, 0.90, 1.0) * (core + glow) * tw;
}

void main()
{
    float aspect = u_res.x / u_res.y;
    vec2 p = gl_FragCoord.xy / u_res.y;
    float px = 1.0 / u_res.y;
    float t = u_time;

    vec3 col = background(p, aspect);
    col += lightRays(p, t);
    col += ribbon(p, t, 0.36, 0.22, 0.0, vec3(0.55, 0.70, 1.00), px);
    col += ribbon(p, t, 0.31, 0.35, 2.4, vec3(0.70, 0.55, 1.00), px);
    for (int i = 0; i < 4; i++)
        col += bubbleLayer(p, t, float(i), px);
    col += stars(p, aspect, t, px);

    vec2 v = gl_FragCoord.xy / u_res - 0.5;
    col *= 1.0 - 0.7 * dot(v, v);              // vinheta
    col *= smoothstep(0.0, 2.5, t);            // fade-in ao iniciar
    col += (hash12(gl_FragCoord.xy + fract(t)) - 0.5) / 255.0;  // dither contra banding
    gl_FragColor = vec4(col, 1.0);
}
