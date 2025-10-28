import { Session } from "./sessionModel.js";
import { Translation } from "./translationModel.js";
import { SystemLog } from "./systemLogModel.js";

//Relaciones entre modelos

// Establecer la relacion entre Session y Translation
Session.hasMany(Translation, { foreignKey: "sessionId" });
// Establecer la relacion entre Translation y Session
Translation.belongsTo(Session, { foreignKey: "sessionId" });

//Relacion entre session y systemLogs
Session.hasMany(SystemLog, { foreignKey: "sessionId" });
SystemLog.belongsTo(Session, { foreignKey: "sessionId" });