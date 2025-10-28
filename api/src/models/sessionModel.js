import { DataTypes } from "sequelize";
import { sequelize } from "../../database.js";
import { Translation } from "./translationModel.js";

export const Session = sequelize.define(
  "sessions",
  {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true,
    },
    startTime: {
      type: DataTypes.DATE,
      allowNull: false,
    },
    endTime: {
      type: DataTypes.DATE,
      allowNull: false,
    },
  },
  { timestamps: true }
);