// Raymarching .frag test
// Author: lo_syn
//gen-shader

#ifdef GL_ES
precision mediump float;
#endif

uniform vec2 u_resolution; // width and height (in pixels) of the rendering target
uniform float u_time; // number of seconds since the shader started running
uniform float u_x0; // input parameter 0
uniform float u_x1; // wave amplitude control (0-1)
uniform float u_x2; // wave frequency control (0-1)
uniform float u_x3; // input parameter 3 

float sdSphere(vec3 p, float s){
    // Sphere SDF
    return length(p) - s; // distance to a sphere of radius s
}
float sdBox( vec3 p, vec3 b){
    // Box SDF
    vec3 q = abs(p) - b;
    return length(max(q,0.0)) + min(max(q.x,max(q.y,q.z)),0.0);
}
float smin( float a, float b, float k ){
    // Smooth minimum function
    // k controls the smoothness of the transition between a and b
    // larger k = smoother transition
    float h = max( k-abs(a-b), 0.0)/k;
    return min( a, b ) - h*h*h*k*(1.0/6.0);
}
mat2 rot2D(float angle){
    // 2D rotation matrix
    float s = sin(angle);
    float c = cos(angle);
    return mat2(c, -s, s, c);
}

vec3 rot3D(vec3 p, vec3 axis,  float angle){
    // Rodrigues' rotation formula for rotating a point p around an arbitrary axis by a given angle
    return mix(dot(axis, p) * axis, p, cos(angle))
    + cross(axis, p) * sin(angle);
}

// Distance to the scene
float map(vec3 p, float sphereX, float waveAmplitude, float waveFrequency, float wavePhase, mat2 rotation){

    vec3 spherePos = vec3(sphereX, 0., 0.); // position of the sphere
    vec3 sphereP = p - spherePos;
    vec3 sphereBase = sphereP;
    sphereP.x += waveAmplitude * sin(waveFrequency * sphereBase.y + wavePhase);
    sphereP.y += waveAmplitude * sin(waveFrequency * sphereBase.z + wavePhase + 2.094);
    sphereP.z += waveAmplitude * sin(waveFrequency * sphereBase.x + wavePhase + 4.189);
    float sphere = sdSphere(sphereP, 1.); // Sphere SDF
    
    vec3 q = p; // Input copy
    q.xy *= rotation; // Rotate around the z-axis
    vec3 boxBase = q;
    q.x += waveAmplitude * sin(waveFrequency * boxBase.y + wavePhase);
    q.y += waveAmplitude * sin(waveFrequency * boxBase.z + wavePhase + 2.094);
    q.z += waveAmplitude * sin(waveFrequency * boxBase.x + wavePhase + 4.189);

    // Scale the box to make it further away and divide by inverse of scaling factor to remove artifacts
    float box = sdBox(q, vec3(.75)); // Box SDF
    // float ground = p.y + 0.75;; // Ground plane SDF
    
    // Closest distance to the scene is the minimum of the two distances
    return smin(box, sphere, 2.); // Smooth minimum of the two distances
}

float normalSin(float val){
    // Create sin wave that oscillates between 0 and 1 instead of -1 and 1
    return sin(val) * 0.5 + 0.5;
}

vec3 palette( float t ){
    vec3 a = vec3(0.78, 0.78, 0.82);
    vec3 b = vec3(0.18, 0.16, 0.18);
    vec3 c = vec3(1.0, 1.0, 1.0);
    vec3 d = vec3(0.00, 0.33, 0.67);
    return a + b*cos(6.28318*(c*t+d));
}

void main() {
    float colour_multi = u_x0 * 5.;
    float waveAmplitude = 0.2 * u_x1;
    float waveFrequency = 1.0 + 14.0 * u_x2;
    float wavePhase = u_time * 2.0;
    float timeSin = sin(u_time);
    float timeCos = cos(u_time);
    mat2 cameraRotation = mat2(timeCos, -timeSin, timeSin, timeCos);
    vec2 uv = (gl_FragCoord.xy * 2. - u_resolution.xy) / u_resolution.y;

    // Initialization
    vec3 ro = vec3(0., 0., -3.); // ray origin
    float fov = 1.0; // field of view
    vec3 rd = normalize(vec3(uv*fov, 1.)); // ray direction
    vec3 col = vec3(0.);

    // Horizontal camera rotation
    float infinite = normalSin(u_time*5.);
    ro.xz *= cameraRotation;
    rd.xz *= cameraRotation;

    float t = 0.; // total distance travelled
    
    // Raymarching
    for ( int i = 0; i < 80; i++){
        vec3 p = ro + rd * t; // position along the ray
        float d = map(p, timeSin, waveAmplitude, waveFrequency, wavePhase, cameraRotation); // current distance to the scene

        t += d; // "march" the ray

        col = vec3(i) / 80.;

        if (d < .001 || t > 100.) break; // early stop if close enough / too far
    }

    // Colouring
    col = palette(t*colour_multi); // colour based on distance travelled


    gl_FragColor = vec4(col, 1.0);
  }