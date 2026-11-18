OF_GLSL_SHADER_HEADER

uniform vec2 resolution;
out vec4 outputColor;

void main()
{
	vec2 uv = gl_FragCoord.xy / resolution;
	outputColor = vec4(uv.x, uv.y, 1.0, 1.0);
}
