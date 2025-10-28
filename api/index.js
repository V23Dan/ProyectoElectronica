import app from "./app.js";
import { createServer } from "http";
import { Server } from "socket.io";
import { sequelize } from "./database.js";
//Modelos a sincronizar
import { Session } from "./src/models/sessionModel.js";
import { Translation } from "./src/models/translationModel.js";
import { Calibration } from "./src/models/calibrationModel.js";
import { SystemLog } from "./src/models/system-logsModel.js";

const httpServer = createServer(app);
const io = new Server(httpServer);

try {
  // Configurar Socket.io
  io.on("connection", (socket) => {
    console.log("a user connected");
  });

  // Probar la conexion a la base de datos
  sequelize.authenticate();
  console.log("Conexion con la base de datos establecida con exito");

  // Sincronizar modelos con la base de datos
  await sequelize.sync({ force: true });

  httpServer.listen(3000, () => {
    console.log("Server is running on port 3000");
  });
} catch (error) {
  console.error("Error al iniciar el API:", error);
}
