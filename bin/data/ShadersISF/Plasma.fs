/*{
  "DESCRIPTION": "Animated plasma generator",
  "CREDIT": "ISF Example",
  "ISFVSN": "2",
  "INPUTS": [
    {
      "NAME": "speed",
      "LABEL": "Speed",
      "TYPE": "float",
      "DEFAULT": 1.0,
      "MIN": 0.0,
      "MAX": 5.0
    },
    {
      "NAME": "scale",
      "LABEL": "Scale",
      "TYPE": "float",
      "DEFAULT": 6.0,
      "MIN": 1.0,
      "MAX": 20.0
    }
  ]
}*/

void main() {
  vec2 uv = gl_FragCoord.xy / RENDERSIZE.xy;
  float t = TIME * speed;

  float v1 = sin(uv.x * scale + t);
  float v2 = sin((uv.y * scale + t) * 0.7);
  float v3 = sin((uv.x + uv.y) * scale * 0.5 - t);
  float wave = (v1 + v2 + v3) / 3.0;

  vec3 col = 0.5 + 0.5 * cos(t + wave * 3.14159 + vec3(0.0, 2.0, 4.0));
  gl_FragColor = vec4(col, 1.0);
}