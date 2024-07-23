from flask import Blueprint, render_template, Response, request, jsonify
from project import db  # DB 연결
from project.models import Cracked_ball  # Cracked_ball 모델 가져오기
import cv2
import numpy as np
from datetime import datetime

# 카메라 초기화
bp = Blueprint('work', __name__, url_prefix='/work')

# 전역 변수 선언 및 초기화
frame_data = b''
cracked_frame_data = b''
camera_running = False
img_running = False

def generate_frames():
    global frame_data
    while True:
        if not frame_data:
            continue
        np_frame = np.frombuffer(frame_data, np.uint8)
        img = cv2.imdecode(np_frame, cv2.IMREAD_COLOR)
        if img is None or img.size == 0:
            continue  # 이미지가 비어 있으면 건너뜁니다.
        ret, buffer = cv2.imencode('.jpg', img)
        if ret:
            frames = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frames + b'\r\n')

def generate_cracked_frames():
    global cracked_frame_data
    while True:
        if not cracked_frame_data:
            continue
        np_frame = np.frombuffer(cracked_frame_data, np.uint8)
        img = cv2.imdecode(np_frame, cv2.IMREAD_COLOR)
        if img is None or img.size == 0:
            continue  # 이미지가 비어 있으면 건너뜁니다.
        ret, buffer = cv2.imencode('.jpg', img)
        if ret:
            frames = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frames + b'\r\n')

@bp.route('/video_stream')
def video_stream():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@bp.route('/cracked_image_stream')
def cracked_image_stream():
    return Response(generate_cracked_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@bp.route('/run-script', methods=['POST'])
def run_script():
    global camera_running, img_running
    camera_running = True
    img_running = True
    print("Camera streaming started")
    return "Camera streaming started"

@bp.route('/stop-script', methods=['POST'])
def stop_script():
    global camera_running, img_running
    camera_running = False
    img_running = False
    global frame_data, cracked_frame_data
    frame_data = b''
    cracked_frame_data = b''
    print("Camera streaming stopped")
    return "Camera streaming stopped"

@bp.route('/raspberry', methods=['POST', 'GET'])
def raspberry():
    if request.method == 'POST':
        global cracked_frame_data
        cracked_frame_data = request.data
        print("Received cracked image data:", len(cracked_frame_data))
        return Response(status=200)
    elif request.method == 'GET':
        return "This endpoint is for receiving cracked image data via POST requests."
    
@bp.route('/camera_display', methods=['POST', 'GET'])
def camera_display():
    if request.method == 'POST':
        global frame_data
        frame_data = request.data
        print("Received camera frame data:", len(frame_data))
        return Response(status=200)
    elif request.method == 'GET':
        return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@bp.route('/increment_crack_count', methods=['POST'])
def increment_crack_count():
    cracked_ball = Cracked_ball(cracked_ball=1, date=datetime.now())
    db.session.add(cracked_ball)
    db.session.commit()
    return "Crack count incremented", 200

@bp.route('/get_crack_count', methods=['GET'])
def get_crack_count():
    count = Cracked_ball.query.count()
    return jsonify(count=count)

@bp.route('/reset_crack_count', methods=['POST'])
def reset_crack_count():
    db.session.query(Cracked_ball).delete()
    db.session.commit()
    return "Crack count reset", 200