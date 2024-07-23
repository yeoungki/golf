import cv2
import numpy as np
import requests
from multiprocessing import shared_memory, Semaphore
import time
import pigpio
import threading

# PWM 핀 번호
pwm_pin = 18

# pigpio 객체 초기화
pi = pigpio.pi()
if not pi.connected:
    print("pigpio 라이브러리를 초기화할 수 없습니다.")
    exit()

# 서보 모터 제어 함수
def set_servo_angle(angle):
    # 각도 범위 제한 (0도 ~ 180도)
    if angle < 0:
        angle = 0
    elif angle > 180:
        angle = 180

    # 펄스 폭 계산 (500μs에서 2500μs 사이)
    pulse_width = int((angle / 180.0) * 2000) + 500
    pi.set_servo_pulsewidth(pwm_pin, pulse_width)
    print("각도 설정: {}도, 펄스 폭: {}μs".format(angle, pulse_width))

def control_servo_motor():
    global motor_busy
    motor_busy = True  # 서보 모터가 동작 중임을 표시
    set_servo_angle(45)  # 서보 모터를 45도로 이동
    time.sleep(30)  # 30초 동안 대기
    set_servo_angle(0)  # 서보 모터를 0도로 이동
    motor_busy = False  # 서보 모터가 동작 완료됨을 표시

# 서보 모터 종료
def cleanup_servo():
    pi.set_servo_pulsewidth(pwm_pin, 0)
    pi.stop()

def iou(b1, B2):
    inter_rect_x1 = np.maximum(b1[0], B2[:, 0])
    inter_rect_y1 = np.maximum(b1[1], B2[:, 1])
    inter_rect_x2 = np.minimum(b1[2], B2[:, 2])
    inter_rect_y2 = np.minimum(b1[3], B2[:, 3])

    inter_area = np.maximum(inter_rect_x2 - inter_rect_x1, 0) * np.maximum(inter_rect_y2 - inter_rect_y1, 0)
    area_b1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
    area_b2 = (B2[:, 2] - B2[:, 0]) * (B2[:, 3] - B2[:, 1])
    iou = inter_area / np.maximum((area_b1 + area_b2 - inter_area), 1e-6)
    return iou

def decoding(pred):
    #[x, y, w, h] to [x1, y1, x2, y2]
    shape_boxes = np.zeros(pred[:, :, :4].shape)
    shape_boxes[:, :, 0] = pred[:, :, 0] - pred[:, :, 2] / 2
    shape_boxes[:, :, 1] = pred[:, :, 1] - pred[:, :, 3] / 2
    shape_boxes[:, :, 2] = pred[:, :, 0] + pred[:, :, 2] / 2
    shape_boxes[:, :, 3] = pred[:, :, 1] + pred[:, :, 3] / 2
    return shape_boxes

def restore(output, image_shape, new_unpad):
    output[:, 0] *= image_shape[1] / new_unpad[0]
    output[:, 1] *= image_shape[0] / new_unpad[1]
    output[:, 2] *= image_shape[1] / new_unpad[0]
    output[:, 3] *= image_shape[0] / new_unpad[1]

# 모델 경로
path_model = 'balltest.onnx'
net = cv2.dnn.readNetFromONNX(path_model)

# 클래스 이름 리스트 유지
class_names = ['crack']

# 쉐어드 메모리 및 세마포어 연결
frame_shape = (480, 640, 3)  # 예시로 480x640 크기의 프레임
# 공유 메모리가 생성될 때까지 대기
while True:
    try:
        shm = shared_memory.SharedMemory(name='frame_shared_memory')
        break
    except FileNotFoundError:
        time.sleep(1)  # 1초 대기 후 다시 시도

shared_frame = np.ndarray(frame_shape, dtype=np.uint8, buffer=shm.buf)
sem = Semaphore(1)

# Flask 서버 URL 설정
server_url = 'http://192.168.1.207:5000/work/raspberry'

start_time = time.time()
motor_busy = False  # motor_busy 변수 초기화
# ... 기존 코드 ...

try:
    while True:
        # 세마포어를 사용하여 공유 메모리에 접근
        sem.acquire()
        frame = shared_frame.copy()
        sem.release()

        current_time = time.time()
        elapsed_time = current_time - start_time

        # 5초마다 프레임 캡처 및 예측 수행
        if elapsed_time > 5:
            start_time = current_time

            height, width = frame.shape[:2]
            center_x, center_y = width // 2, height // 2
            radius = 70  # 반지름을 70 픽셀로 설정

            # 원형 마스크 생성
            mask = np.zeros((height, width), dtype=np.uint8)
            cv2.circle(mask, (center_x, center_y), radius, 255, -1)

            # 마스크를 사용하여 원 내부는 원래 프레임을 유지하고 나머지는 검정색으로 처리
            result = cv2.bitwise_and(frame, frame, mask=mask)

            image_shape = result.shape[:2]
            image = cv2.resize(result, (640, 640), interpolation=cv2.INTER_LINEAR)
            image = image.transpose((2, 0, 1))[::-1]  # HWC to CHW, BGR to RGB
            image = np.ascontiguousarray(image)
            image = image[None]
            image = image / 255.0

            # 모델 추론
            net.setInput(image)
            pred = net.forward()

            # 디코딩
            pred[:, :, :4] = decoding(pred)
            output = []

            for i in range(pred.shape[0]):
                prediction = pred[i]
                mask = (prediction[:, 4] > 0.5)
                # 초기 선별 신뢰도가 0.5보다 큽니다.
                prediction = prediction[mask]
                class_conf, class_pred = np.expand_dims(np.max(prediction[:, 5:], 1), -1), np.expand_dims(np.argmax(prediction[:, 5:], 1), -1)
                # 카테고리 점수
                detections = np.concatenate((prediction[:, :5], class_conf, class_pred), 1)

                unique_class = np.unique(detections[:, -1])
                best_box = []

                # 비최대 억제
                for c in unique_class:
                    cls_mask = detections[:, -1] == c
                    detection = detections[cls_mask]
                    # 같은 종류
                    arg_sort = np.argsort(detection[:, 4])[::-1]
                    detection = detection[arg_sort]
                    # 점수가 큰 것부터 작은 것 순으로 정렬
                    while np.shape(detection)[0] > 0:
                        best_box.append(detection[0])
                        if len(detection) == 1:
                            break
                        # 상자와 동일한 유형의 다음 상자를 모두 계산합니다.
                        ious = iou(best_box[-1], detection[1:])
                        detection = detection[1:][ious < 0.2]
                # iou > 0.4 제거됨
                output.append(best_box)

            output = np.array(output)
            output = np.squeeze(output, axis=0)

            # 원본 이미지 비율로 복원
            if output.ndim > 1:
                restore(output, image_shape, (640, 640))

            crack_detected = False

            # 이미지에 결과 그리기
            for i in output:
                result = cv2.rectangle(result, (int(i[0]), int(i[1])), (int(i[2]), int(i[3])), (255, 0, 0), 2)
                result = cv2.putText(result, "%s:%.2f" % (class_names[int(i[-1])], i[-2]), (int(i[0]), int(i[1])), cv2.FONT_HERSHEY_COMPLEX, 0.5, (0, 255, 0), 1)
                crack_detected = True

            # 크랙이 감지되었을 때 메시지 표시 및 이미지 전송
            if crack_detected and not motor_busy:
                print("크랙이 감지되었습니다.")
                threading.Thread(target=control_servo_motor).start()
                _, img_encoded = cv2.imencode('.jpg', result)
                response = requests.post(server_url, data=img_encoded.tobytes(), headers={'Content-Type': 'application/octet-stream'})
                if response.status_code == 200:
                    print("이미지 전송 성공")
                else:
                    print("이미지 전송 실패")
            else:
                # 크랙이 감지되지 않았을 때 초기화된 이미지를 전송
                print("크랙이 감지되지 않았습니다.")
                blank_image = np.zeros_like(result)
                _, img_encoded = cv2.imencode('.jpg', blank_image)
                response = requests.post(server_url, data=img_encoded.tobytes(), headers={'Content-Type': 'application/octet-stream'})
                if response.status_code == 200:
                    print("초기화된 이미지 전송 성공")
                else:
                    print("초기화된 이미지 전송 실패")
                

                

finally:
    shm.close()
    shm.unlink()
    cleanup_servo()  # 서보 모터 종료