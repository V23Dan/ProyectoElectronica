import { sequelize } from "../../database.js";
import { DataTypes } from "sequelize";

export const Calibration = sequelize.define(
  "calibration",
  {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true,
    },
    distanceThreshold: {
      type: DataTypes.FLOAT,
      allowNull: false,
    },
    confidenceThreshold: {
      type: DataTypes.FLOAT,
      allowNull: false,
    },
  },
  { timestamps: true }
);
