import cv2
import sys
import os
import time
import json

from app.services.video_processor import VideoProcessor

def print_menu():
    print("\n" + "="*50)
    print("SISTEMA DE DETECCIÓN DE LENGUAJE DE SEÑAS")
    print("="*50)
    print("1. Conectar automáticamente (recomendado)")
    print("2. Listar cámaras disponibles")
    print("3. Conectar a cámara específica")
    print("4. Cambiar cámara")
    print("5. Reiniciar clasificador (r)")
    print("6. Mostrar estado del sistema")
    print("7. Salir (q)")
    print("-"*50)

def main():
    print("Iniciando sistema avanzado de detección de señas...")
    
    # Inicializar video processor
    vp = VideoProcessor()
    
    # Conectar automáticamente
    print("-----Buscando cámaras disponibles...")
    if vp.initialize_camera(auto_connect=True):
        print("Cámara conectada automáticamente")
    else:
        print("No se pudo conectar automáticamente a ninguna cámara")
        print("Por favor, conecta una cámara manualmente")
    
    camera_running = vp.camera_manager.is_connected
    
    print("\nControles en ventana de video:")
    print("  'q' - Salir")
    print("  'r' - Reiniciar clasificador")
    print("  'c' - Cambiar cámara")
    print("  's' - Mostrar estado")
    
    last_status_check = 0
    
    while True:
        if not camera_running:
            print("No hay cámara conectada. Use el menú para conectar una.")
            time.sleep(2)
            continue
        
        # Procesar frame
        processed_frame, prediction, confidence = vp.process_next_frame()
        
        if processed_frame is not None:
            # Mostrar frame
            cv2.imshow('Sistema Avanzado - Detección de Señas', processed_frame)
            
            # Mostrar predicción en consola cada 2 segundos
            current_time = time.time()
            if current_time - last_status_check >= 2.0:
                status = vp.get_camera_status()
                print(f"\r {status['name']} |  {prediction} ({confidence:.2f}) | {status['fps']} FPS", end="")
                last_status_check = current_time
        
        # Manejar teclas
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            vp.reset_classifier()
            print("\n Clasificador reiniciado")
        elif key == ord('c'):
            print("\n Cambiando de cámara...")
            cameras = vp.get_available_cameras()
            if len(cameras) > 1:
                # Cambiar a la siguiente cámara
                current_cam = vp.camera_manager.current_camera
                current_index = cameras.index(current_cam) if current_cam in cameras else -1
                next_index = (current_index + 1) % len(cameras)
                success = vp.switch_camera(cameras[next_index])
                if success:
                    print(f" Cambiado a: {cameras[next_index]['name']}")
                else:
                    print(" Error al cambiar de cámara")
            else:
                print(" Solo hay una cámara disponible")
        elif key == ord('s'):
            status = vp.get_camera_status()
            print(f"\n Estado del sistema:")
            print(f"   Cámara: {status.get('name', 'Desconocida')}")
            print(f"   Tipo: {status.get('type', 'Desconocido')}")
            print(f"   Estado: {status.get('status', 'Desconocido')}")
            print(f"   FPS: {status.get('fps', 0):.1f}")
            print(f"   Frames procesados: {status.get('frames_processed', 0)}")
            print(f"   Tiempo procesamiento: {status.get('processing_time', 0)*1000:.1f}ms")
        
        # Verificar si la cámara sigue conectada
        camera_running = vp.camera_manager.is_connected
    
    # Liberar recursos
    vp.close()
    cv2.destroyAllWindows()
    print("\n👋 Sistema terminado correctamente")

def camera_selection_menu(vp):
    """Menú para selección manual de cámaras"""
    while True:
        print("\n Escaneando cámaras...")
        cameras = vp.get_available_cameras()
        
        if not cameras:
            print(" No se encontraron cámaras disponibles")
            return False
        
        print(f"\n Cámaras disponibles ({len(cameras)} encontradas):")
        for i, cam in enumerate(cameras):
            print(f"  {i+1}. {cam['name']}")
            print(f"     Tipo: {cam['type']} | Resolución: {cam.get('resolution', 'N/A')}")
        
        print(f"  {len(cameras)+1}. Volver al menú principal")
        
        try:
            choice = int(input("\nSelecciona una cámara: "))
            if 1 <= choice <= len(cameras):
                success = vp.connect_to_camera(cameras[choice-1])
                if success:
                    print(f" Conectado a: {cameras[choice-1]['name']}")
                    return True
                else:
                    print(" Error al conectar con la cámara seleccionada")
            elif choice == len(cameras) + 1:
                return False
            else:
                print(" Opción inválida")
        except ValueError:
            print(" Por favor, ingresa un número válido")

if __name__ == "__main__":
    main()