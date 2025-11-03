import os

class Config:
    # Configuración de cámaras
    CAMERA_CONFIGS = {
        "laptop": {
            "width": 640,
            "height": 480,
            "fps": 30
        },
        "esp32": {
            "width": 640,
            "height": 480, 
            "fps": 10
        }
    }
    
    # URLs comunes de ESP32-CAM
    ESP32_URLS = [
        "http://192.168.1.100:81/stream",
        "http://192.168.4.1:81/stream", 
        "http://esp32cam.local/stream",
        "http://192.168.1.100/video",
        "http://192.168.1.100:8080/video"
    ]
    
    # Configuración del modelo
    MODEL_CONFIG = {
        "sequence_length": 30,
        "confidence_threshold": 0.7,
        "min_hand_confidence": 0.5
    }
    
    # Configuración de video
    VIDEO_CONFIG = {
        "flip_horizontal": True,
        "show_debug_info": True,
        "max_fps": 30
    }

# Instancia de configuración global
config = Config()