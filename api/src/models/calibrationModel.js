import { sequelize } from "../../database.js";
import { DataTypes } from "sequelize";

export const Calibration = sequelize.define(
  "Calibration",
  {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true,
    },
    distanceTreshold: {
      type: DataTypes.FLOAT,
      allowNull: false,
    },
    confidenceTreshold: {
      type: DataTypes.FLOAT,
      allowNull: false,
    },
  },
  { timestamps: true }
);
