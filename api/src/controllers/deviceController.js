import WebSocket from "ws";

class DeviceController {
  constructor() {
    this.esp32Connections = new Map();
    this.distanceThreshold = { min: 50, max: 150, optimal: 100 };
    this.io = null; 
    this.currentDistance = null;
    this.personDetected = false;
    this.lastUpdate = Date.now();
  }

  // Configurar Socket.io (para comunicación con frontend)
  setSocketIO(io) {
    this.io = io;
    console.log("Socket.IO configurado en DeviceController");
  }

  // WebSocket para comunicación con ESP32-WROVER
  setupDeviceWebSocket(server) {
    const wss = new WebSocket.Server({ server, path: "/ws/device" });
    console.log("WebSocket Server para dispositivos iniciado en /ws/device");

    wss.on("connection", (ws, req) => {
      const deviceId = req.socket.remoteAddress + ":" + req.socket.remotePort;
      console.log(`ESP32-WROVER conectado: ${deviceId}`);

      this.esp32Connections.set(deviceId, {
        ws,
        lastSeen: Date.now(),
        distance: null,
        personDetected: false,
      });

      // Enviar mensaje de bienvenida
      this.sendToDevice(deviceId, {
        type: "status",
        message: "CONECTADO",
      });

      // Notificar al frontend
      if (this.io) {
        this.io.emit("device_connected", { deviceId, timestamp: new Date() });
      }

      // Manejar mensajes del dispositivo
      ws.on("message", (data) => {
        try {
          const message = JSON.parse(data);
          this.handleDeviceMessage(deviceId, message);
        } catch (error) {
          console.error("Error parsing device message:", error);
        }
      });

      // Manejar desconexión
      ws.on("close", () => {
        console.log(` ESP32-WROVER desconectado: ${deviceId}`);
        this.esp32Connections.delete(deviceId);

        if (this.io) {
          this.io.emit("device_disconnected", {
            deviceId,
            timestamp: new Date(),
          });
        }
      });

      ws.on("error", (error) => {
        console.error(`Error en WS del dispositivo ${deviceId}:`, error);
      });
    });

    // Limpieza periódica de conexiones inactivas
    setInterval(() => this.cleanupInactiveConnections(), 30000);
  }

  // Manejar mensajes del dispositivo
  handleDeviceMessage(deviceId, message) {
    const device = this.esp32Connections.get(deviceId);
    if (!device) return;

    device.lastSeen = Date.now();

    switch (message.type) {
      case "distance":
        this.handleDistanceData(deviceId, message);
        break;

      case "alert":
        this.handleAlert(deviceId, message.message);
        break;

      case "status":
        console.log(`Estado de ${deviceId}: ${message.message}`);
        break;

      default:
        console.log("Mensaje desconocido del dispositivo:", message);
    }
  }

  // Manejar datos de distancia
  handleDistanceData(deviceId, data) {
    const distance = data.value;
    const personDetected = data.person_detected;

    // Actualizar estado del dispositivo
    const device = this.esp32Connections.get(deviceId);
    if (device) {
      device.distance = distance;
      device.personDetected = personDetected;
    }

    this.currentDistance = distance;
    this.personDetected = personDetected;

    // Enviar al frontend en tiempo real
    if (this.io) {
      this.io.emit("distance_update", {
        deviceId,
        distance,
        personDetected,
        timestamp: new Date(),
        status: this.getDistanceStatus(distance),
      });
    }

    // Lógica de feedback al usuario
    this.provideDistanceFeedback(deviceId, distance, personDetected);
  }

  // Determinar estado de la distancia
  getDistanceStatus(distance) {
    if (distance < this.distanceThreshold.min) {
      return "TOO_CLOSE";
    } else if (distance > this.distanceThreshold.max) {
      return "TOO_FAR";
    } else if (Math.abs(distance - this.distanceThreshold.optimal) <= 20) {
      return "OPTIMAL";
    } else {
      return "ACCEPTABLE";
    }
  }

  // Proveer feedback basado en distancia
  provideDistanceFeedback(deviceId, distance, personDetected) {
    if (!personDetected) {
      return;
    }
  }

  // Manejar alertas del dispositivo
  handleAlert(deviceId, alertMessage) {
    console.log(`Alerta de ${deviceId}: ${alertMessage}`);

    // Enviar alerta al frontend
    if (this.io) {
      this.io.emit("device_alert", {
        deviceId,
        message: alertMessage,
        timestamp: new Date(),
      });
    }

    // Lógica específica según la alerta
    if (alertMessage === "PERSONA_DETECTADA") {
      this.onPersonDetected(deviceId);
    } else if (alertMessage === "PERSONA_SALIO") {
      this.onPersonLeft(deviceId);
    }
  }

  // Evento: Persona detectada
  onPersonDetected(deviceId) {
    console.log(`Persona detectada en ${deviceId}`);

    if (this.io) {
      this.io.emit("start_translation", {
        deviceId,
        timestamp: new Date(),
      });
    }

    this.sendToDevice(deviceId, {
      type: "status",
      message: "TRADUCIENDO",
    });
  }

  onPersonLeft(deviceId) {
    console.log(`Persona salió del rango en ${deviceId}`);

    if (this.io) {
      this.io.emit("stop_translation", {
        deviceId,
        timestamp: new Date(),
      });
    }

    this.sendToDevice(deviceId, {
      type: "status",
      message: "DETENIDO",
    });

    this.sendDisplayMessage(deviceId, "Esperando...");
  }

  sendToDevice(deviceId, message) {
    const device = this.esp32Connections.get(deviceId);
    if (device && device.ws.readyState === WebSocket.OPEN) {
      device.ws.send(JSON.stringify(message));
      return true;
    }
    return false;
  }

  sendDisplayMessage(deviceId, text) {
    return this.sendToDevice(deviceId, {
      type: "display",
      message: text,
    });
  }

  broadcastToDevices(message) {
    let sent = 0;
    this.esp32Connections.forEach((device, deviceId) => {
      if (this.sendToDevice(deviceId, message)) {
        sent++;
      }
    });
    return sent;
  }

  setLED(deviceId, state) {
    return this.sendToDevice(deviceId, {
      type: "led",
      command: state ? "ON" : "OFF",
    });
  }

  setServoAngle(deviceId, angle) {
    if (angle < 0 || angle > 180) {
      console.error("Ángulo de servo inválido:", angle);
      return false;
    }
    return this.sendToDevice(deviceId, {
      type: "servo",
      angle: angle,
    });
  }

  cleanupInactiveConnections() {
    const now = Date.now();
    const timeout = 60000; 

    this.esp32Connections.forEach((device, deviceId) => {
      if (now - device.lastSeen > timeout) {
        console.log(`🧹 Limpiando conexión inactiva: ${deviceId}`);
        device.ws.close();
        this.esp32Connections.delete(deviceId);
      }
    });
  }

  // Obtener lista de dispositivos conectados
  getConnectedDevices() {
    const devices = [];
    this.esp32Connections.forEach((device, deviceId) => {
      devices.push({
        id: deviceId,
        distance: device.distance,
        personDetected: device.personDetected,
        lastSeen: new Date(device.lastSeen),
        connected: device.ws.readyState === WebSocket.OPEN,
      });
    });
    return devices;
  }

  // Obtener estado actual
  getStatus() {
    return {
      connectedDevices: this.esp32Connections.size,
      currentDistance: this.currentDistance,
      personDetected: this.personDetected,
      thresholds: this.distanceThreshold,
      lastUpdate: new Date(this.lastUpdate),
    };
  }

  updateThresholds(min, max, optimal) {
    this.distanceThreshold = {
      min: min || this.distanceThreshold.min,
      max: max || this.distanceThreshold.max,
      optimal: optimal || this.distanceThreshold.optimal,
    };
    console.log("Umbrales actualizados:", this.distanceThreshold);
  }

  showTranslation(deviceId, text, confidence) {
    const displayText = `${text}\nConf: ${(confidence * 100).toFixed(0)}%`;
    return this.sendDisplayMessage(deviceId, displayText);
  }

  broadcastTranslation(text, confidence) {
    return this.broadcastToDevices({
      type: "display",
      message: `${text}\nConf: ${(confidence * 100).toFixed(0)}%`,
    });
  }
}

const deviceController = new DeviceController();

export default deviceController;
