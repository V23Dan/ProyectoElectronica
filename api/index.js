import app from "./app.js";
import { createServer } from "http";
import { Server } from "socket.io";
import { sequelize } from "./database.js";
//Modelos a sincronizar
import { Session } from "./src/models/sessionModel.js";
import { Translation } from "./src/models/translationModel.js";
import { Calibration } from "./src/models/calibrationModel.js";
import { SystemLog } from "./src/models/system-logsModel.js";

//Controladores
import deviceController from "./src/controllers/deviceController.js";
import systemController from "./src/controllers/systemController.js";

const httpServer = createServer(app);
const io = new Server(httpServer, {
  cors: {
    origin: [
      "http://localhost:3000",
      "http://localhost:5173",
      "http://localhost:5174",
    ],
    methods: ["GET", "POST"],
    credentials: true,
  },
});

//Configurar Esp32
deviceController.setupDeviceWebSocket(httpServer);

deviceController.setSocketIO(io);
systemController.setSocketIO(io);

// Socket.IO eventos
io.on("connection", (socket) => {
  console.log("🔌 Cliente frontend conectado:", socket.id);

  // Enviar estado inicial
  socket.emit("system_status", systemController.getSystemStatus());
  socket.emit("device_status", deviceController.getStatus());

  // Solicitar estado
  socket.on("request_status", () => {
    socket.emit("system_status", systemController.getSystemStatus());
    socket.emit("device_status", deviceController.getStatus());
  });

  // Control de dispositivos
  socket.on("control_led", (data) => {
    const { deviceId, state } = data;
    deviceController.setLED(deviceId, state);
  });

  socket.on("control_servo", (data) => {
    const { deviceId, angle } = data;
    deviceController.setServoAngle(deviceId, angle);
  });

  socket.on("send_display_message", (data) => {
    const { deviceId, message } = data;
    deviceController.sendDisplayMessage(deviceId, message);
  });

  socket.on("disconnect", () => {
    console.log("Cliente frontend desconectado:", socket.id);
  });
});

//SERVIDOR
const PORT = process.env.PORT || 3000;

async function startServer() {
  try {
    await sequelize.authenticate();
    console.log("Conexion con la base de datos establecida con exito");
    await sequelize.sync({ alter: true });

    await systemController.initialize();

    console.log("Conexion con la base de datos establecida con exito");

    httpServer.listen(PORT, () => {
      console.log("Server is running on port ", PORT);
    });
  } catch (error) {
    console.error("Error al iniciar el API:", error);
    process.exit(1);
  }
}

startServer();

export { httpServer, io };
