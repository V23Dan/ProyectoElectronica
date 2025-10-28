import { sequelize } from "../../database.js";
import { DataTypes } from "sequelize";

export const SystemLog = sequelize.define(
  "system_logs",
  {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true,
    },
    sessionId: {
      type: DataTypes.INTEGER,
      allowNull: false,
      references: {
        model: "sessions",
        key: "id",
      },
    },
    eventType: {
      type: DataTypes.STRING,
      allowNull: false,
    },
    message: {
      type: DataTypes.TEXT,
      allowNull: false,
    },
    severity: {
      type: DataTypes.STRING,
      allowNull: false,
    },
  },
  { timestamps: true }
);
