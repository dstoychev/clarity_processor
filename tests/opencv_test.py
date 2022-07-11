import numpy as np
import cv2
import aurox_clarity.processor as cproc
import time

N=100

# Try first calibration image
img = cv2.imread('tests/calib_h.tiff',cv2.IMREAD_ANYDEPTH)
# img = cv2.imread('calibration_0.png',cv2.IMREAD_GRAYSCALE)
cv2.imshow('input image',img)

e0 = cv2.getTickCount()

cp = cproc.Processor(img)

e1 = cv2.getTickCount()

res = cp.process(img,0.95)

e2 = cv2.getTickCount()

t = (e1 - e0)/cv2.getTickFrequency()
print('Calibration time ',t)
t = (e2 - e1)/cv2.getTickFrequency()
print('Processing time ',t)

result=cv2.multiply(res,100)

cv2.imshow('Registered and subtracted image',result)

# Try second test calibration image
img2 = cv2.imread('tests/calib_rot_h.tiff',cv2.IMREAD_ANYDEPTH)
e0 = cv2.getTickCount()
cp2 = cproc.Processor(img2)
e1 = cv2.getTickCount()
res2 = cp2.process_gpu3(img2,0.95)
e2 = cv2.getTickCount()
cv2.imshow('2nd image...',cv2.multiply(res2,10))
t = (e1 - e0)/cv2.getTickFrequency()
print('Calibration time ',t)
t = (e2 - e1)/cv2.getTickFrequency()
print('Processing time ',t)

# Benchmark different processing routines

# Original code (runs on GPU)
# Pass numpy image, take subimages then convert to UMat
time.sleep(5)
e0 = cv2.getTickCount()

for i in range(N) :
    res2=cp2.process(img2,0.95)

e1 = cv2.getTickCount()

t = (e1 - e0)/cv2.getTickFrequency()
print(N,'original gpu loop ',1000*t/N,' ms')

# Original code (runs on CPU)
time.sleep(5)
e0 = cv2.getTickCount()

for i in range(N) :
    res2=cp2.process_cpu(img2,0.95)

e1 = cv2.getTickCount()
t = (e1 - e0)/cv2.getTickFrequency()
print(N,'cpu loop ',1000*t/N,' ms')

# GPU, passing 1 numpy image, convert to UMat, then take subimages
time.sleep(5)
e0 = cv2.getTickCount()

for i in range(N) :
    res2=cp2.process_gpu2(img2,0.95)

e1 = cv2.getTickCount()

t = (e1 - e0)/cv2.getTickFrequency()
print(N,'gpu2 loop ',1000*t/N,' ms')

# GPU, passing 1 numpy image, convert to UMat, then take subimages, use scaleAdd routine
time.sleep(5)
e0 = cv2.getTickCount()

for i in range(N) :
    res2=cp2.process_gpu3(img2,0.95)

e1 = cv2.getTickCount()

t = (e1 - e0)/cv2.getTickFrequency()
print(N,'gpu3 loop ',1000*t/N,' ms')

# CPU, passing 1 numpy image, multiply and add
time.sleep(5)
e0 = cv2.getTickCount()

for i in range(N) :
    res2=cp2.process_cpu1(img2,0.95)

e1 = cv2.getTickCount()

t = (e1 - e0)/cv2.getTickFrequency()
print(N,'cpu1 loop ',1000*t/N,' ms')

# GPU but passing 2 UMat images
time.sleep(5)
width=int(np.size(img2,1)/2)
img_l=cv2.UMat(img2[:,0:width])
img_r=cv2.UMat(img2[:,width:])
e0 = cv2.getTickCount()

for i in range(N) :
    res2=cp2.process_gpu1(img_l,img_r,0.95)

e1 = cv2.getTickCount()

t = (e1 - e0)/cv2.getTickFrequency()
print(N,'gpu1 loop ',1000*t/N,' ms')

res3 = cp.process(img2,0.95)
cv2.imshow('Wrong calibration!',cv2.multiply(res3,10))

cv2.waitKey(0)
