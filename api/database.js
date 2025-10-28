import { Sequelize } from "sequelize";

// Configurar la conexion a la base de datos
export const sequelize = new Sequelize("TraductionSigns", "postgres", "admin", {
  host: "localhost",
  dialect: "postgres",
});