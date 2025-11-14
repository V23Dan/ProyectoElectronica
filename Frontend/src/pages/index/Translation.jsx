import React, { useEffect, useRef, useState } from "react";
import { useSocket } from "../../context/SocketContext";
import {
  Play,
  Square,
  RotateCcw,
  Camera,
  Activity,
  Zap,
  Settings,
} from "lucide-react";
import "./Translation.css";

const Translation = () => {
  const { videoSocket, isConnected, systemStatus, sendControlCommand } =
    useSocket();

  const videoCanvasRef = useRef(null);
  const [currentTranslation, setCurrentTranslation] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [translationsHistory, setTranslationsHistory] = useState([]);
  const [cameraInfo, setCameraInfo] = useState({});
  const [showAdvancedInfo, setShowAdvancedInfo] = useState(false);
  const [stats, setStats] = useState({
    fps: 0,
    processingTime: 0,
    framesProcessed: 0,
  });

  // 🧠 Manejar mensajes entrantes del WebSocket de video
  useEffect(() => {
    if (!videoSocket) return;

    const handleMessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "video_frame") {
          // 🎥 Renderizar frame en canvas
          if (data.frame && videoCanvasRef.current) {
            const ctx = videoCanvasRef.current.getContext("2d");
            const img = new Image();
            img.onload = () => {
              ctx.clearRect(
                0,
                0,
                videoCanvasRef.current.width,
                videoCanvasRef.current.height
              );
              ctx.drawImage(
                img,
                0,
                0,
                videoCanvasRef.current.width,
                videoCanvasRef.current.height
              );
            };
            img.src = data.frame;
          }

          // ✋ Actualizar predicción
          if (data.prediction) {
            setCurrentTranslation(data.prediction);
            setConfidence(data.confidence || 0);

            // Guardar en historial si confianza es alta
            if (
              data.confidence > 0.7 &&
              data.prediction !== "NO_HANDS_DETECTED"
            ) {
              setTranslationsHistory((prev) => [
                {
                  text: data.prediction,
                  confidence: data.confidence,
                  timestamp: new Date().toLocaleTimeString(),
                },
                ...prev.slice(0, 9),
              ]);
            }
          }

          // 🎛️ Actualizar info de cámara y métricas
          setCameraInfo(data.camera_info || {});
          setStats({
            fps: data.fps || 0,
            processingTime: data.processing_time || 0,
            framesProcessed: (prev) => prev.framesProcessed + 1,
          });
        } else if (data.type === "camera_status") {
          setCameraInfo(data.camera_status || {});
        }
      } catch (err) {
        console.error("Error procesando mensaje de video:", err);
      }
    };

    videoSocket.addEventListener("message", handleMessage);
    return () => videoSocket.removeEventListener("message", handleMessage);
  }, [videoSocket]);

  // 🔘 Controladores
  const handleStartSession = () => {
    setIsProcessing(true);
    sendControlCommand("start_session");
  };

  const handleStopSession = () => {
    setIsProcessing(false);
    sendControlCommand("stop_session");
  };

  const handleResetClassifier = () => {
    sendControlCommand("reset_classifier");
    setTranslationsHistory([]);
    setCurrentTranslation("");
    setConfidence(0);
  };

  const handleGetStatus = () => sendControlCommand("get_status");

  const getConfidenceColor = (conf) => {
    if (conf > 0.8) return "#10b981"; // verde
    if (conf > 0.6) return "#f59e0b"; // amarillo
    return "#ef4444"; // rojo
  };

  // 🟢 Pedir estado al conectarse
  useEffect(() => {
    if (isConnected) handleGetStatus();
  }, [isConnected]);

  return (
    <div className="translation-page">
      <div className="translation-layout">
        {/* === SECCIÓN PRINCIPAL === */}
        <div className="main-display">
          {/* --- VIDEO --- */}
          <div className="video-section">
            <div className="video-container">
              <div className="video-header">
                <Camera size={20} />
                <h2>Video en Tiempo Real</h2>
                <div className="connection-badge">
                  <div
                    className={`status-indicator ${
                      isConnected ? "connected" : "disconnected"
                    }`}
                  />
                  {isConnected ? "Conectado" : "Desconectado"}
                </div>
              </div>

              <div className="video-wrapper">
                <canvas
                  ref={videoCanvasRef}
                  width="640"
                  height="480"
                  className="video-canvas"
                />
                <div className="video-overlay">
                  <div className="overlay-item fps">
                    FPS: {stats.fps?.toFixed(1) || "0"}
                  </div>
                  <div className="overlay-item camera">
                    {cameraInfo?.name || "Cámara activa"}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* --- TRADUCCIÓN --- */}
          <div className="translation-section">
            <div className="current-translation">
              <div className="translation-header">
                <Activity size={20} />
                <h2>Traducción Actual</h2>
                <button
                  className="info-toggle"
                  onClick={() => setShowAdvancedInfo(!showAdvancedInfo)}
                >
                  <Settings size={16} />
                </button>
              </div>

              <div className="translation-content">
                <div className="translation-text">
                  {currentTranslation || "Esperando detección..."}
                </div>

                {/* Barra de confianza */}
                <div className="confidence-section">
                  <div className="confidence-bar">
                    <div
                      className="confidence-fill"
                      style={{
                        width: `${confidence * 100}%`,
                        backgroundColor: getConfidenceColor(confidence),
                      }}
                    />
                  </div>
                  <span className="confidence-value">
                    {Math.round(confidence * 100)}% confianza
                  </span>
                </div>

                {/* Estado básico */}
                <div className="status-indicators">
                  <div className="status-item">
                    <Zap size={16} />
                    <span>
                      Estado: {isConnected ? "Conectado" : "Desconectado"}
                    </span>
                  </div>
                  {cameraInfo?.name && (
                    <div className="status-item">
                      <Camera size={16} />
                      <span>Cámara: {cameraInfo.name}</span>
                    </div>
                  )}
                </div>

                {/* Info avanzada */}
                {showAdvancedInfo && (
                  <div className="advanced-info">
                    <div className="info-grid">
                      <div className="info-item">
                        <label>FPS:</label>
                        <span>{stats.fps?.toFixed(1) || "0"}</span>
                      </div>
                      <div className="info-item">
                        <label>Procesamiento:</label>
                        <span>
                          {(stats.processingTime * 1000).toFixed(1)} ms
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* === CONTROLES === */}
        <div className="controls-section">
          <div className="video-controls">
            <button
              className={`control-btn ${isProcessing ? "stop" : "start"}`}
              onClick={isProcessing ? handleStopSession : handleStartSession}
              disabled={!isConnected}
            >
              {isProcessing ? <Square size={16} /> : <Play size={16} />}
              {isProcessing ? "Detener" : "Comenzar"}
            </button>

            <button
              className="control-btn secondary"
              onClick={handleResetClassifier}
              disabled={!isConnected}
            >
              <RotateCcw size={16} />
              Reiniciar Clasificador
            </button>

            <button
              className="control-btn secondary"
              onClick={handleGetStatus}
              disabled={!isConnected}
            >
              <Activity size={16} />
              Estado
            </button>
          </div>
        </div>

        {/* === HISTORIAL === */}
        <div className="history-section">
          <div className="history-container">
            <div className="history-header">
              <h3>Historial de Traducciones</h3>
              <span>{translationsHistory.length} registros</span>
            </div>

            <div className="translations-list">
              {translationsHistory.length === 0 ? (
                <div className="empty-history">
                  <p>No hay traducciones recientes</p>
                </div>
              ) : (
                translationsHistory.map((t, i) => (
                  <div key={i} className="translation-item">
                    <div className="translation-main">
                      <span>{t.text}</span>
                      <span
                        className="confidence-badge"
                        style={{
                          backgroundColor: getConfidenceColor(t.confidence),
                        }}
                      >
                        {Math.round(t.confidence * 100)}%
                      </span>
                    </div>
                    <div className="translation-meta">{t.timestamp}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Translation;
