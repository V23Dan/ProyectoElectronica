import { Calibration } from '../models/calibrationModel.js';
import { SystemLog } from '../models/system-logsModel.js';
import deviceController from './deviceController.js';
import { Op } from 'sequelize';

class SystemController {
  constructor() {
    this.currentCalibration = null;
    this.systemStatus = {
      pythonMicroservice: false,
      database: false,
      esp32Base: false,
      esp32Cam: false
    };
  }

  async initialize() {
    try {
      await this.loadActiveCalibration();
      
      console.log('System Controller inicializado');
      return true;
    } catch (error) {
      console.error('Error inicializando System Controller:', error);
      return false;
    }
  }

  async loadActiveCalibration() {
    try {
      const calibration = await Calibration.findOne({
        order: [['createdAt', 'DESC']]
      });

      if (calibration) {
        this.currentCalibration = {
          id: calibration.id,
          distanceThreshold: calibration.distanceThreshold,
          confidenceThreshold: calibration.confidenceThreshold
        };
        
        deviceController.updateThresholds(
          this.currentCalibration.distanceThreshold - 50,
          this.currentCalibration.distanceThreshold + 50,
          this.currentCalibration.distanceThreshold
        );

        console.log('Calibración cargada:', this.currentCalibration);
      } else {
        const defaultCalibration = await Calibration.create({
          distanceThreshold: 100.0,
          confidenceThreshold: 0.7
        });

        this.currentCalibration = {
          id: defaultCalibration.id,
          distanceThreshold: 100.0,
          confidenceThreshold: 0.7
        };

        console.log('Calibración por defecto creada');
      }
    } catch (error) {
      console.error('Error cargando calibración:', error);
      throw error;
    }
  }

  async updateCalibration(distanceThreshold, confidenceThreshold) {
    try {
      const newCalibration = await Calibration.create({
        distanceThreshold: distanceThreshold,
        confidenceThreshold: confidenceThreshold
      });

      this.currentCalibration = {
        id: newCalibration.id,
        distanceThreshold,
        confidenceThreshold
      };

      deviceController.updateThresholds(
        distanceThreshold - 50,
        distanceThreshold + 50,
        distanceThreshold
      );

      console.log('Calibración actualizada:', this.currentCalibration);
      
      return {
        success: true,
        calibration: this.currentCalibration
      };
    } catch (error) {
      console.error('Error actualizando calibración:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  getCurrentCalibration() {
    return this.currentCalibration;
  }

  async logSystemEvent(sessionId, eventType, message, severity = 'INFO') {
    try {
      await SystemLog.create({
        sessionId,
        eventType,
        message,
        severity
      });
      
      console.log(` [${severity}] ${eventType}: ${message}`);
    } catch (error) {
      console.error('Error registrando evento:', error);
    }
  }

  async checkSystemHealth() {
    const health = {
      database: false,
      pythonMicroservice: false,
      esp32Base: false,
      timestamp: new Date()
    };

    try {
      await Calibration.findOne();
      health.database = true;
    } catch (error) {
      console.error('Base de datos no disponible');
    }

    const devices = deviceController.getConnectedDevices();
    health.esp32Base = devices.length > 0;

    health.pythonMicroservice = false;

    this.systemStatus = health;
    return health;
  }

  getSystemStatus() {
    return {
      ...this.systemStatus,
      calibration: this.currentCalibration,
      devices: deviceController.getConnectedDevices(),
      deviceStatus: deviceController.getStatus()
    };
  }

  async restartComponent(component) {
    switch (component) {
      case 'esp32':
        const devices = deviceController.getConnectedDevices();
        if (devices.length > 0) {
          deviceController.broadcastToDevices({
            type: 'command',
            action: 'restart'
          });
          return { success: true, message: 'Comando de reinicio enviado al ESP32' };
        }
        return { success: false, message: 'No hay dispositivos ESP32 conectados' };

      case 'calibration':
        await this.loadActiveCalibration();
        return { success: true, message: 'Calibración recargada' };

      default:
        return { success: false, message: 'Componente desconocido' };
    }
  }

  setSocketIO(io) {
    this.io = io;
    
    setInterval(async () => {
      const status = this.getSystemStatus();
      this.io.emit('system_status_update', status);
    }, 5000); 
  }

  async getSessionLogs(sessionId, limit = 50) {
    try {
      const logs = await SystemLog.findAll({
        where: { sessionId },
        order: [['createdAt', 'DESC']],
        limit
      });
      
      return logs;
    } catch (error) {
      console.error('Error obteniendo logs:', error);
      return [];
    }
  }

  async getSystemStats() {
    try {
      const totalCalibrations = await Calibration.count();
      const totalLogs = await SystemLog.count();
      const recentLogs = await SystemLog.count({
        where: {
          createdAt: {
            [Op.gte]: new Date(Date.now() - 24 * 60 * 60 * 1000)
          }
        }
      });

      return {
        totalCalibrations,
        totalLogs,
        recentLogs,
        currentCalibration: this.currentCalibration,
        uptime: process.uptime()
      };
    } catch (error) {
      console.error('Error obteniendo estadísticas:', error);
      return null;
    }
  }
}

const systemController = new SystemController();

export default systemController;