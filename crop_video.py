import cv2
import argparse


ap = argparse.ArgumentParser()
ap.add_argument("-v", "--video", required=True, help = "path to the video to stabilize")
ap.add_argument("-o", "--output", default='.', help="path to dir to save video and transformation files")
args = vars(ap.parse_args())

def crop_img(img, scale=1.0):
    center_x, center_y = img.shape[1] / 2, img.shape[0] / 2
    width_scaled, height_scaled = img.shape[1] * scale, img.shape[0] * scale
    left_x, right_x = center_x - width_scaled / 2, center_x + width_scaled / 2
    top_y, bottom_y = center_y - height_scaled / 2, center_y + height_scaled / 2
    img_cropped = img[int(top_y):int(bottom_y), int(left_x):int(right_x)]
    return img_cropped
    

cap = cv2.VideoCapture(args['video'])
N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps = int(cap.get(cv2.CAP_PROP_FPS))

status, prev = cap.read()
(h,w) = prev.shape[:2]
crop_scale = 0.75
h_scale = int(h*crop_scale)
w_scale = int(w*crop_scale)

out = cv2.VideoWriter('{}/cropped_output.avi'.format(args['output']), 
	cv2.VideoWriter_fourcc('P','I','M','1'), fps, (w_scale, h_scale), True)


for k in range(N-1):
    status, img = cap.read()
    img_cropped = crop_img(img, crop_scale)
    cv2.imshow('cropped', img_cropped)
    cv2.waitKey(20)
    out.write(img_cropped)




