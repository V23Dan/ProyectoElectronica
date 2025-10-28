import { sequelize } from "../../database.js";
import { DataTypes } from "sequelize";

import { Session } from "./sessionModel.js";

export const Translation = sequelize.define(
  "translations",
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
    textOutput: {
      type: DataTypes.TEXT,
      allowNull: false,
    },
    confidence: {
      type: DataTypes.FLOAT,
      allowNull: false,
    },
  },
  { timestamps: true }
);
