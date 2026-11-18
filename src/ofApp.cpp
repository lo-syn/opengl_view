#include "ofApp.h"

#include <cmath>

namespace {
constexpr int oscPort = 8001;
}

//--------------------------------------------------------------
void ofApp::setup(){
	const auto shaderDirectory = ofIsGLProgrammableRenderer()
		? "shadersGL3"
		: "shadersGL2";
	const auto vertexShaderPath = ofToDataPath(std::string(shaderDirectory) + "/shader.vert");
	const auto fragmentShaderPath = ofToDataPath(std::string(shaderDirectory) + "/blog.frag");
	shaderLoaded = shader.load(vertexShaderPath, fragmentShaderPath);
	if(!shaderLoaded){
		ofLogError("ofApp::setup") << "Failed to load shaders from " << shaderDirectory;
	}

	if(!oscReceiver.setup(oscPort)){
		ofLogError("ofApp::setup") << "Failed to listen for OSC on port " << oscPort;
	}
}

//--------------------------------------------------------------
void ofApp::update(){
	while(oscReceiver.hasWaitingMessages()){
		ofxOscMessage message;
		if(!oscReceiver.getNextMessage(message)){
			continue;
		}
		const auto address = message.getAddress();
		float* shaderValue = nullptr;
		if(address == "/u_x0"){
			shaderValue = &shaderX0;
		}else if(address == "/u_x1"){
			shaderValue = &shaderX1;
		}else if(address == "/u_x2"){
			shaderValue = &shaderX2;
		}else{
			continue;
		}
		if(message.getNumArgs() != 1){
			ofLogWarning("ofApp::update") << "Expected one numeric argument for " << address;
			continue;
		}

		const auto type = message.getArgType(0);
		if(type != OFXOSC_TYPE_FLOAT && type != OFXOSC_TYPE_INT32){
			ofLogWarning("ofApp::update") << "Expected a float or integer argument for " << address;
			continue;
		}

		const float value = message.getArgAsFloat(0);
		if(!std::isfinite(value)){
			ofLogWarning("ofApp::update") << "Ignoring non-finite value for " << address;
			continue;
		}
		*shaderValue = value;
	}
}

//--------------------------------------------------------------
void ofApp::draw(){
	ofBackground(0);
	if(!shaderLoaded){
		return;
	}

	ofSetColor(255);
	const auto viewport = ofGetNativeViewport();
	shader.begin();
	shader.setUniform2f("u_resolution", viewport.width, viewport.height);
	shader.setUniform1f("u_time", ofGetElapsedTimef());
	shader.setUniform1f("u_x0", shaderX0);
	shader.setUniform1f("u_x1", shaderX1);
	shader.setUniform1f("u_x2", shaderX2);
	ofDrawRectangle(0, 0, ofGetWidth(), ofGetHeight());
	shader.end();
}

//--------------------------------------------------------------
void ofApp::keyPressed(int key){

}

//--------------------------------------------------------------
void ofApp::keyReleased(int key){

}

//--------------------------------------------------------------
void ofApp::mouseMoved(int x, int y){

}

//--------------------------------------------------------------
void ofApp::mouseDragged(int x, int y, int button){

}

//--------------------------------------------------------------
void ofApp::mousePressed(int x, int y, int button){

}

//--------------------------------------------------------------
void ofApp::mouseReleased(int x, int y, int button){

}

//--------------------------------------------------------------
void ofApp::mouseEntered(int x, int y){

}

//--------------------------------------------------------------
void ofApp::mouseExited(int x, int y){

}

//--------------------------------------------------------------
void ofApp::windowResized(int w, int h){

}

//--------------------------------------------------------------
void ofApp::gotMessage(ofMessage msg){

}

//--------------------------------------------------------------
void ofApp::dragEvent(ofDragInfo dragInfo){ 

}