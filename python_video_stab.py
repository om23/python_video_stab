#SCRIPT TO PERFORM VIDEO STABILIZATION.  
#	INPUTS: VIDEO FILE
#	OUTPUTS: STABELIZED VIDEO AVI, TRANSFORMATION DF CSV, SMOOTHED TRAJECTORY CSV

#RESOURCE & ORIGINAL CPP AUTHOR OF THIS VIDEO STAB LOGIC: http://nghiaho.com/?p=2093
#ORIGINAL CPP: http://nghiaho.com/uploads/code/videostab.cpp

#example usage:
#	python python_video_stab.py --video input_video.mov --output output --compareOutput 1 --maxWidth 400
import cv2
import numpy as np
import pandas as pd
import argparse
import imutils
import sys
import time

# TODO: 
#	- [Done] Visual process status
#	- build functions instead of script format
#	- look into performance improvements
#	- [Done] get size of frames
#	- [Done] trim frame to certain size, by %?
#	- Make cropping an argument ot pass in
#	- Maybe cropping isn't the best solution, should be doing something to try minimizing times the frame is out of center (black background)
#	- For cropping, have scale values relative to common frame sizes
# 		- maxWidth defs (not accurate since only width): 1280 (720p), 1920 (1080p), 3840 (2160p - 4k)



# construct the argument parse and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-v", "--video", required=True, help = "path to the video to stabilize")
ap.add_argument("-o", "--output", default='.', help="path to dir to save video and transformation files")
ap.add_argument("-c", "--compareOutput", default=1, type=int, help="should output be a side by side comparison")
ap.add_argument("-w", "--maxWidth", default=400, type=int, help="max width of output video")
args = vars(ap.parse_args())



def crop_img(img, scale=1.0):
    center_x, center_y = img.shape[1] / 2, img.shape[0] / 2
    width_scaled, height_scaled = img.shape[1] * scale, img.shape[0] * scale
    left_x, right_x = center_x - width_scaled / 2, center_x + width_scaled / 2
    top_y, bottom_y = center_y - height_scaled / 2, center_y + height_scaled / 2
    img_cropped = img[int(top_y):int(bottom_y), int(left_x):int(right_x)]
    return img_cropped

# derived from: https://stackoverflow.com/questions/3160699/python-progress-bar#3160819 
def update_progress(total, progress):
    barLength, status = 20, ""
    progress = float(progress) / float(total)
    if progress >= 1.:
        progress, status = 1, "\r\n"
    block = int(round(barLength * progress))
    text = "\r[{}] {:.0f}% {}".format(
        "#" * block + "-" * (barLength - block), round(progress * 100, 0),
        status)
    sys.stdout.write(text)
    sys.stdout.flush()


print "Part 1: Setting up video capture and calculating STAB"


#####
# CALC T MAT FOR STAB
#set up video capture
cap = cv2.VideoCapture(args['video'])
N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps = int(cap.get(cv2.CAP_PROP_FPS))
crop_scale = 0.75



#read first frame
status, prev = cap.read()
#convert to gray scale
prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
#get image dims
(h,w) = prev.shape[:2]

#initialize storage
prev_to_cur_transform = []
#iterate through frame count
for k in range(N-1):
	#read current frame
	status, cur = cap.read()
	#convert to gray
	cur_gray = cv2.cvtColor(cur, cv2.COLOR_BGR2GRAY)
	#use GFTT for keypoint detection
	prev_corner = cv2.goodFeaturesToTrack(prev_gray, maxCorners = 200, qualityLevel = 0.01, minDistance = 30.0, blockSize = 3)
	#calc flow of movement (resource: http://opencv-python-tutroals.readthedocs.io/en/latest/py_tutorials/py_video/py_lucas_kanade/py_lucas_kanade.html)
	cur_corner, status, err = cv2.calcOpticalFlowPyrLK(prev_gray, cur_gray, prev_corner,None)
	#storage for keypoints with status 1
	prev_corner2 = []
	cur_corner2 = []
	for i,st in enumerate(status):
		#if keypoint found in frame i & i-1
		if st==1:
			#store coords of keypoints that appear in both
			prev_corner2.append(prev_corner[i])
			cur_corner2.append(cur_corner[i])
	prev_corner2 = np.array(prev_corner2)
	cur_corner2 = np.array(cur_corner2)
	#estimate partial transform (resource: http://nghiaho.com/?p=2208)
	T_new = cv2.estimateRigidTransform(prev_corner2, cur_corner2, False)
	if T_new is not None:
		T = T_new
	#translation x
	dx = T[0,2]
	#translation y
	dy = T[1,2]
	#rotation
	da = np.arctan2(T[1,0], T[0,0])
	#store for saving to disk as table
	prev_to_cur_transform.append([dx, dy, da])
	#set current frame to prev frame for use in next iteration
	prev = cur[:]
	prev_gray = cur_gray[:]
	update_progress(N, k + 1) 

#convert list of transforms to array
prev_to_cur_transform = np.array(prev_to_cur_transform)
#cumsum of all transforms for trajectory
trajectory = np.cumsum(prev_to_cur_transform, axis=0)

#convert trajectory array to df
trajectory = pd.DataFrame(trajectory)
#rolling mean to smooth
smoothed_trajectory = trajectory.rolling(window=30,center=False).mean()
#back fill nas caused by smoothing
smoothed_trajectory = smoothed_trajectory.fillna(method='bfill')
#save smoothed trajectory
smoothed_trajectory.to_csv('{}/smoothed.csv'.format(args['output']))

#new set of prev to cur transform, removing trajectory and replacing w/smoothed
new_prev_to_cur_transform = prev_to_cur_transform + (smoothed_trajectory - trajectory)
#write transforms to disk
new_prev_to_cur_transform.to_csv('{}/new_prev_to_cur_transformation.csv'.format(args['output']))

#####
# APPLY VIDEO STAB
#####
#initialize transformation matrix
T = np.zeros((2,3))
#convert transform df to array
new_prev_to_cur_transform = np.array(new_prev_to_cur_transform)
#setup video cap
cap = cv2.VideoCapture(args['video'])
#set output width based on option for saving old & stabilized video side by side
w_write = min(w, args['maxWidth'])
#correct height change caused by width change
h_write = imutils.resize(prev_gray, width = w_write).shape[0]
#double output width if option chosen for side by side comparison
if args['compareOutput'] > 0:
	w_write = w_write*2
#setup video writer
w_scale = int(w_write*crop_scale)
h_scale = int(h_write*crop_scale)
out = cv2.VideoWriter('{}/stabilized_output.avi'.format(args['output']), 
	cv2.VideoWriter_fourcc('P','I','M','1'), fps, (w_scale, h_scale), True)

print "\nPart 2: Looping through frames"

#loop through frame count
for k in range(N-1):
	#read current frame
	status, cur = cap.read()
	#read/build transformation matrix
	T[0,0] = np.cos(new_prev_to_cur_transform[k][2])
	T[0,1] = -np.sin(new_prev_to_cur_transform[k][2])
	T[1,0] = np.sin(new_prev_to_cur_transform[k][2])
	T[1,1] = np.cos(new_prev_to_cur_transform[k][2])
	T[0,2] = new_prev_to_cur_transform[k][0]
	T[1,2] = new_prev_to_cur_transform[k][1]
	#apply saved transform (resource: http://nghiaho.com/?p=2208)
	cur2 = cv2.warpAffine(cur, T, (w,h))
	#build side by side comparison if option chosen
	if args['compareOutput'] > 0:
		#resize to maxwidth (if current width larger than maxwidth)
		cur_resize = imutils.resize(cur, width = min(w, args['maxWidth']))
		#resize to maxwidth (if current width larger than maxwidth)
		cur2_resize = imutils.resize(cur2, width = min(w, args['maxWidth']))
		#combine arrays for side by side
		cur2 = np.hstack((cur_resize, cur2_resize))
	else:
		#resize to maxwidth (if current width larger than maxwidth)
		cur2 = imutils.resize(cur2, width = min(w, args['maxWidth']))
	
	#show frame to screen
	# cv2.imshow('stable', cur2)
	# cv2.waitKey(20)
	img_cropped = crop_img(cur2, crop_scale)
	#write frame to output video
	# out.write(cur2)
	out.write(img_cropped)
	update_progress(N, k + 1)

print("\nDone")
