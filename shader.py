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
in vec3 randSeed;                             // random seed for random placement ( (0,0,0) if coodinates are used directly)
in float disparityFactor;                     // scaling for xEye (1 if normal disparity is shown, 0 for no disparity)
in float size;                                // linear size of stars
out vec2 sizeClip;                            // size in clip coordinates

//
// Description : Array and textureless GLSL 2D simplex noise function.
//      Author : Ian McEwan, Ashima Arts.
//  Maintainer : ijm
//     Lastmod : 20110822 (ijm)
//     License : Copyright (C) 2011 Ashima Arts. All rights reserved.
//               Distributed under the MIT License. See LICENSE file.
//               https://github.com/ashima/webgl-noise
// 

vec3 mod289(vec3 x) {
  return x - floor(x * (1.0 / 289.0)) * 289.0;
}

vec2 mod289(vec2 x) {
  return x - floor(x * (1.0 / 289.0)) * 289.0;
}

vec3 permute(vec3 x) {
  return mod289(((x*34.0)+1.0)*x);
}

float snoise(vec2 v)  {
  // simplex noise, The next Perlin noise algorithm
  const vec4 C = vec4(0.211324865405187,  // (3.0-sqrt(3.0))/6.0
                      0.366025403784439,  // 0.5*(sqrt(3.0)-1.0)
                     -0.577350269189626,  // -1.0 + 2.0 * C.x
                      0.024390243902439); // 1.0 / 41.0
// First corner
  vec2 i  = floor(v + dot(v, C.yy) );
  vec2 x0 = v -   i + dot(i, C.xx);

// Other corners
  vec2 i1;
  //i1.x = step( x0.y, x0.x ); // x0.x > x0.y ? 1.0 : 0.0
  //i1.y = 1.0 - i1.x;
  i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
  // x0 = x0 - 0.0 + 0.0 * C.xx ;
  // x1 = x0 - i1 + 1.0 * C.xx ;
  // x2 = x0 - 1.0 + 2.0 * C.xx ;
  vec4 x12 = x0.xyxy + C.xxzz;
  x12.xy -= i1;

// Permutations
  i = mod289(i); // Avoid truncation effects in permutation
  vec3 p = permute( permute( i.y + vec3(0.0, i1.y, 1.0 ))
		+ i.x + vec3(0.0, i1.x, 1.0 ));

  vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
  m = m*m ;
  m = m*m ;

// Gradients: 41 points uniformly over a line, mapped onto a diamond.
// The ring size 17*17 = 289 is close to a multiple of 41 (41*7 = 287)

  vec3 x = 2.0 * fract(p * C.www) - 1.0;
  vec3 h = abs(x) - 0.5;
  vec3 ox = floor(x + 0.5);
  vec3 a0 = x - ox;

// Normalise gradients implicitly by scaling m
// Approximation of: m *= inversesqrt( a0*a0 + h*h );
  m *= 1.79284291400159 - 0.85373472095314 * ( a0*a0 + h*h );

// Compute final noise value at P
  vec3 g;
  g.x  = a0.x  * x0.x  + h.x  * x0.y;
  g.yz = a0.yz * x12.xz + h.yz * x12.yw;
  return 130.0 * dot(m, g);
}

mat4 MVP(float x, float y){
	// same as above, but now for objects connected to to moving observer
	return mat4(
		2*focal/width,              0,                     0,                        0,
		            0, 2*focal/height,                     0,                        0,
		   -2*x/width,    -2*y/height, (far+near)/(near-far),                       -1,
		x*moveFactor*2*focal/width, 0, (2*far*near-focal*(far+near))/(near-far), focal
		//            0,              0, (2*far*near-focal*(far+near))/(near-far), focal
		);
}

void main() {
	vec4 p = vec4(position, 1.0);
	vec3 min = vec3(-width/2, -height/2, focal-far);
	vec3 max = vec3(width/2, height/2, focal-near);
	float disparityFactorFactor = 0.0;
	for(int i=0; i<3; i++)
		if (randSeed[i] != 0)
			//p[i] += min[i]+(max[i]-min[i])*(snoise(vec2(float(nFrame), randSeed[i])));
			p[i] += 2.3*max[i]*(snoise(vec2(float(nFrame), randSeed[i])));
	//if (disparityFactor != 0 || disparityFactor !=1)
        //        disparityFactorFactor = 5*snoise(vec2(float(nFrame), disparityFactor));
        //else
        //        disparityFactorFactor = disparityFactor;
	mat4 M = MVP(x+disparityFactor * xEye, y);
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
