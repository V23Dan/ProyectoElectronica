import WebSocket from 'ws';
import {SerialPort} from 'serialport';

class DeviceController {
  constructor() {
    this.esp32Connections = new Map();
    this.distanceThreshold = { min: 50, max: 150 }; // cm
  }

  // WebSocket para comunicación con ESP32-WROVER
  setupDeviceWebSocket(server) {
    const wss = new WebSocket.Server({ server, path: '/ws/device' });

    wss.on('connection', (ws, req) => {
      const deviceId = req.socket.remoteAddress;
      console.log(`ESP32-WROVER conectado: ${deviceId}`);
      
      this.esp32Connections.set(deviceId, ws);
      
      ws.on('message', (data) => {
        try {
          const message = JSON.parse(data);
          this.handleDeviceMessage(deviceId, message);
        } catch (error) {
          console.error('Error parsing device message:', error);
        }
      });

      ws.on('close', () => {
        console.log(`ESP32-WROVER desconectado: ${deviceId}`);
        this.esp32Connections.delete(deviceId);
      });

      // Enviar mensaje de inicialización
      ws.send(JSON.stringify({ type: 'status', message: 'CONECTADO' }));
    });
  }

  handleDeviceMessage(deviceId, message) {
    switch (message.type) {
      case 'distance':
        this.handleDistanceData(deviceId, message.value);
        break;
      case 'alert':
        this.handleAlert(deviceId, message.message);
        break;
      default:
        console.log('Mensaje desconocido:', message);
    }
  }

  handleDistanceData(deviceId, distance) {
    console.log(`Distancia medida: ${distance} cm`);
    
    // Aquí puedes integrar con el frontend o Python
    // Por ejemplo, enviar a frontend via Socket.io
    if (this.io) {
      this.io.emit('distance_update', { distance, deviceId });
    }

    // Opcional: Enviar a Python si afecta el procesamiento
    if (distance > this.distanceThreshold.max) {
      this.sendToDisplay(deviceId, "ACERCARSE");
    } else if (distance < this.distanceThreshold.min) {
      this.sendToDisplay(deviceId, "ALEJARSE");
    } else {
      this.sendToDisplay(deviceId, "DISTANCIA OK");
    }
  }

  handleAlert(deviceId, alertMessage) {
    console.log(`Alerta de ${deviceId}: ${alertMessage}`);
    // Enviar alerta al frontend
    if (this.io) {
      this.io.emit('device_alert', { deviceId, message: alertMessage });
    }
  }

  sendToDisplay(deviceId, message) {
    const ws = this.esp32Connections.get(deviceId);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(message);
    }
  }

  // Métodos para control desde el frontend
  setDisplayMessage(message) {
    // Enviar a todos los dispositivos conectados
    this.esp32Connections.forEach((ws, deviceId) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(message);
      }
    });
  }

  getConnectedDevices() {
    return Array.from(this.esp32Connections.keys());
  }
}

const deviceController = new DeviceController();
export default deviceController;