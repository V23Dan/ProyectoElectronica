import express from "express";
import cors from "cors";

const app = express();
app.use(express.json());
app.use(cors());

import systemController from "./src/controllers/systemController.js";

//Rutes
// --- HEALTH CHECK ---
app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    service: "LSC Translation Backend",
    version: "1.0.0",
    timestamp: new Date(),
  });
});

// --- SYSTEM STATUS ---
app.get("/api/system/status", async (req, res) => {
  try {
    const status = systemController.getSystemStatus();
    const health = await systemController.checkSystemHealth();

    res.json({
      success: true,
      status,
      health,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});

app.get("/api/system/stats", async (req, res) => {
  try {
    const stats = await systemController.getSystemStats();
    res.json({
      success: true,
      stats,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});

// --- CALIBRATION ---
app.get("/api/calibration", (req, res) => {
  const calibration = systemController.getCurrentCalibration();
  res.json({
    success: true,
    calibration,
  });
});

app.post("/api/calibration", async (req, res) => {
  try {
    const { distanceThreshold, confidenceThreshold } = req.body;

    if (!distanceThreshold || !confidenceThreshold) {
      return res.status(400).json({
        success: false,
        error: "Faltan parámetros de calibración",
      });
    }

    const result = await systemController.updateCalibration(
      distanceThreshold,
      confidenceThreshold
    );

    res.json(result);
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});

app.get("/api/calibration/history", async (req, res) => {
  try {
    const history = await Calibration.findAll({
      order: [["createdAt", "DESC"]],
      limit: 10,
    });

    res.json({
      success: true,
      history,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});

// --- DEVICES ---
app.get("/api/devices", (req, res) => {
  const devices = deviceController.getConnectedDevices();
  res.json({
    success: true,
    devices,
    count: devices.length,
  });
});

app.get("/api/devices/status", (req, res) => {
  const status = deviceController.getStatus();
  res.json({
    success: true,
    status,
  });
});

app.post("/api/devices/:deviceId/display", (req, res) => {
  const { deviceId } = req.params;
  const { message } = req.body;

  if (!message) {
    return res.status(400).json({
      success: false,
      error: "Se requiere un mensaje",
    });
  }

  const sent = deviceController.sendDisplayMessage(
    decodeURIComponent(deviceId),
    message
  );

  res.json({
    success: sent,
    message: sent ? "Mensaje enviado" : "Error enviando mensaje",
  });
});

app.post("/api/devices/:deviceId/led", (req, res) => {
  const { deviceId } = req.params;
  const { state } = req.body;

  const sent = deviceController.setLED(decodeURIComponent(deviceId), state);

  res.json({
    success: sent,
    message: sent ? "LED actualizado" : "Error actualizando LED",
  });
});

app.post("/api/devices/:deviceId/servo", (req, res) => {
  const { deviceId } = req.params;
  const { angle } = req.body;

  if (angle === undefined || angle < 0 || angle > 180) {
    return res.status(400).json({
      success: false,
      error: "Ángulo inválido (0-180)",
    });
  }

  const sent = deviceController.setServoAngle(
    decodeURIComponent(deviceId),
    angle
  );

  res.json({
    success: sent,
    message: sent ? "Servo movido" : "Error moviendo servo",
  });
});

// --- SESSIONS ---
app.get("/api/sessions", async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 20;

    const sessions = await Session.findAll({
      order: [["start_time", "DESC"]],
      limit,
      include: [
        {
          model: Translation,
          as: "translations",
        },
        {
          model: SystemLog,
          as: "system_logs",
        },
      ],
    });

    res.json({
      success: true,
      sessions,
      count: sessions.length,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});

app.get("/api/sessions/:id", async (req, res) => {
  try {
    const { id } = req.params;

    const session = await Session.findByPk(id, {
      include: [
        {
          model: Translation,
          as: "translations",
        },
        {
          model: SystemLog,
          as: "system_logs",
        },
      ],
    });

    if (!session) {
      return res.status(404).json({
        success: false,
        error: "Sesión no encontrada",
      });
    }

    res.json({
      success: true,
      session,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});

app.get("/api/sessions/:id/logs", async (req, res) => {
  try {
    const { id } = req.params;
    const limit = parseInt(req.query.limit) || 50;

    const logs = await systemController.getSessionLogs(id, limit);

    res.json({
      success: true,
      logs,
      count: logs.length,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});

// --- TRANSLATIONS ---
app.get("/api/translations", async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 50;
    const sessionId = req.query.sessionId;

    const where = sessionId ? { sessionId } : {};

    const translations = await Translation.findAll({
      where,
      order: [["createdAt", "DESC"]],
      limit,
      include: [
        {
          model: Session,
          as: "session",
        },
      ],
    });

    res.json({
      success: true,
      translations,
      count: translations.length,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});

app.post("/api/translations", async (req, res) => {
  try {
    const { sessionId, textOutput, confidence } = req.body;

    if (!sessionId || !textOutput || confidence === undefined) {
      return res.status(400).json({
        success: false,
        error: "Faltan parámetros requeridos",
      });
    }

    const translation = await Translation.create({
      sessionId,
      textOutput,
      confidence,
    });

    // Enviar a dispositivos conectados
    deviceController.broadcastTranslation(textOutput, confidence);

    // Notificar al frontend vía Socket.IO
    io.emit("new_translation", {
      translation,
      timestamp: new Date(),
    });

    res.json({
      success: true,
      translation,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});
export default app;
