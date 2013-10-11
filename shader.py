#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Copyright © 2013, W. van Ham, Radboud University Nijmegen
This file is part of Sleelab.

Sleelab is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Sleelab is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Sleelab.  If not, see <http://www.gnu.org/licenses/>.
'''

import sys

from OpenGL.GL.shaders import *
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.arrays import vbo
from OpenGL.GL.shaders import *

def initializeShaders(vertexShaderString, fragmentShaderString, geometryShaderString=None):
	if not glUseProgram:
		print ('Missing Shader Objects!')
		sys.exit(1)
	try:
		vertexShader = compileShader(vertexShaderString, GL_VERTEX_SHADER)
		if geometryShaderString !=None:
			geometryShader = compileShader(geometryShaderString, GL_GEOMETRY_SHADER)
		fragmentShader = compileShader(fragmentShaderString, GL_FRAGMENT_SHADER)
	except RuntimeError as (errorString):
		print ("ERROR: Shaders did not compile properly: {}".format(errorString[0]))
		a = (errorString[1][0]).split('\n')
		for i in range(0,len(a)):
			print ("{0:3d} {1:}".format(i+1, a[i]))
		sys.exit(1)
	try:
		if geometryShaderString !=None:
			program = compileProgram(vertexShader, fragmentShader, geometryShader)
		else:
			program = compileProgram(vertexShader, fragmentShader)
	except RuntimeError as (errorString):
		print("ERROR: Shader program did not link/validate properly: {}".format(errorString))
		sys.exit(1)
	
	glUseProgram(program)
	return program

vs = \
"""#version 330

uniform float width, height, near, focal, far, x, y; // see MVP for explanation
uniform float xEye;                                  // added to x for stereoscopic disparity
//uniform float size;                                  // linear size of stars
uniform int nFrame;                                  // frame number
uniform float moveFactor;                            // relative moving along with the observer of objects

in vec3 position;                             // vertex coordinate
in uvec3 randSeed;                             // random seed for random placement ( (0,0,0) if coodinates are used directly)
in float disparityFactor;                     // scaling for xEye (1 if normal disparity is shown, 0 for no disparity)
in float size;                                // linear size of stars
in uint lifetime;                             // lifetime of star in number of frames
out vec2 sizeClip;                            // size in clip coordinates

uint wang_hash(uint seed){
	seed = (seed ^ 61U) ^ (seed >> 16U);
	seed *= 9U;
	seed = seed ^ (seed >> 4U);
	seed *= 0x27d4eb2dU;
	seed = seed ^ (seed >> 15U);
	return seed;
}

/* generates a random number on [0,1]-real-interval */
float rand(uint seed, float min=0.0, float max=1.0){
	return float(wang_hash(seed))*((max-min)/4294967295.0)+min;
	/* divided by 2^32-1 */ 
}

mat4 MVP(float xSled, float xEye, float y){
	// same as above, but now for objects connected to to moving observer
	return mat4(
		                 2*focal/width,              0,                                        0,    0,
		                             0, 2*focal/height,                                        0,    0,
		         -2*(xSled+xEye)/width,    -2*y/height,                    (far+near)/(near-far),   -1,
		xSled*moveFactor*2*focal/width,              0, (2*far*near-focal*(far+near))/(near-far), focal
		);
}

void main() {
	vec4 p = vec4(position, 1.0);
	float d = 0.40; // maximum horizontal displacement of viewer
	vec3 max = vec3((width/2+d)*far/focal, height/2*far/focal, focal-near);
	vec3 min = vec3(-max.xy, focal-far);
	float disparityFactorFactor = 0.0;
	for(int i=0; i<3; i++)
		if (randSeed[i] != 0U)
			//p[i] += min[i]+(max[i]-min[i])*(snoise(vec2(float(nFrame), randSeed[i])));
			//p[i] += 2.3*max[i]*(snoise(vec2(float(nFrame), randSeed[i])));
			if(lifetime==0U)
				p[i] = 2.0*rand(randSeed[i], min[i], max[i]);
			else
				p[i] = 2.0*rand(((uint(nFrame)+randSeed.x)/lifetime)*0x10000U + randSeed[i], min[i], max[i]);
	//if (disparityFactor != 0 || disparityFactor !=1)
		//disparityFactorFactor = 5*snoise(vec2(float(nFrame), disparityFactor));
	//else
		//disparityFactorFactor = disparityFactor;
	//p.z=0;
	mat4 M = MVP(x, disparityFactor * xEye, y);
	sizeClip = (M*(p+vec4(0.5*size, 0.5*size, 0, 0)) - M*(p-vec4(0.5*size, 0.5*size, 0.0, 0.0))).xy;
	gl_Position = M * p;
}
"""

gs = \
"""#version 330
layout(points) in;
layout(triangle_strip, max_vertices = 3) out;
in vec2 sizeClip[];        // size scaled to eye coordinates
in gl_PerVertex{
  vec4 gl_Position;
  float gl_PointSize;
  float gl_ClipDistance[];
} gl_in[];

vec3 offset[3] = vec3[](
	vec3(-0.5,    -sqrt(3.0)/6.0, 0.0), 
	vec3( 0.5,    -sqrt(3.0)/6.0, 0.0), 
	vec3( 0.0,     sqrt(3.0)/3.0, 0.0));
void main(void) {
	vec3 scale = vec3(sizeClip[0], 1.0);
	for (int i = 0; i < 3; ++i) {
		gl_Position = gl_in[0].gl_Position + vec4(offset[i]*scale, 1.);
		EmitVertex();
	}
	EndPrimitive();
}
"""

fs = \
"""#version 330
uniform vec3 color;
uniform float fadeFactor;   // multiplyer for color (1.0 for faded in, 0.0 for faded out)
void main() {
	gl_FragColor = vec4( fadeFactor*color, 1 );
}
"""
