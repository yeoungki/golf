import cv2
import numpy as np
import requests
from multiprocessing import shared_memory, Semaphore
import RPi.GPIO as GPIO  # GPIO 라이브러리 추가
import threading  # 스레드 라이브러리 추가
import time  # 시간 라이브러리 추가

# 비디오 캡처 초기화
cap = cv2.VideoCapture(0)

# GPIO 설정
GPIO.setmode(GPIO.BCM)
GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # 18번 핀을 입력으로 설정하고 풀업 저항 사용

# 공유 메모리 및 세마포어 생성
frame_shape = (480, 640, 3)  # 예시로 480x640 크기의 프레임
shm_name = 'frame_shared_memory'
try:
    shm = shared_memory.SharedMemory(name=shm_name, create=True, size=np.prod(frame_shape) * np.dtype(np.uint8).itemsize)
    print("공유 메모리 생성")
except FileExistsError:
    shm = shared_memory.SharedMemory(name=shm_name)
    print("기존 공유 메모리 연결")

shared_frame = np.ndarray(frame_shape, dtype=np.uint8, buffer=shm.buf)
sem = Semaphore(1)

# Flask 서버 URL 설정
server_url = 'http://192.168.1.207:5000/work/camera_display'
crack_url = 'http://192.168.1.207:5000/work/increment_crack_count'  # 크랙 카운트 증가 URL

def monitor_switch():
    debounce_time = 0.2  # 디바운스 시간 (초)
    while True:
        if GPIO.input(18) == GPIO.LOW:
            response = requests.post(crack_url)
            if response.status_code == 200:
                print("크랙 카운트 증가 성공")
            else:
                print("크랙 카운트 증가 실패")
            while GPIO.input(18) == GPIO.LOW:
                pass  # 스위치가 눌린 상태에서 대기
            time.sleep(debounce_time)  # 디바운스 시간 동안 대기

# 스위치 감지 스레드 시작
switch_thread = threading.Thread(target=monitor_switch)
switch_thread.daemon = True
switch_thread.start()

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 세마포어를 사용하여 공유 메모리에 접근
        sem.acquire()
        np.copyto(shared_frame, frame)
        sem.release()

        # 프레임을 Flask 서버로 전송
        _, img_encoded = cv2.imencode('.jpg', frame)
        response = requests.post(server_url, data=img_encoded.tobytes(), headers={'Content-Type': 'application/octet-stream'})
        if response.status_code != 200:
            print("프레임 전송 실패")
        else:
            print("프레임 전송 성공")

        # 실시간으로 처리된 영상을 로컬에서 확인하려면 주석 해제
        # cv2.imshow('Processed Frame', frame)
        # if cv2.waitKey(1) & 0xFF == ord('q'):
        #    break
        
finally:
    # 리소스 해제
    cap.release()
    cv2.destroyAllWindows()
    shm.close()
    shm.unlink()
    GPIO.cleanup()  # GPIO 설정 해제
