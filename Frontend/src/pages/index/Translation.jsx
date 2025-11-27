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
  Wifi,
  WifiOff,
  Cpu,
  Volume2,
  VolumeX,
} from "lucide-react";
import "./Translation.css";

const Translation = () => {
  const {
    videoSocket,
    isConnected,
    systemStatus,
    currentSession,
    getStatus,
    resetClassifier,
    startSession,
    stopSession,
  } = useSocket();

  const videoCanvasRef = useRef(null);
  const [currentTranslation, setCurrentTranslation] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [translationsHistory, setTranslationsHistory] = useState([]);
  const [showAdvancedInfo, setShowAdvancedInfo] = useState(false);
  
  // ========== NUEVOS ESTADOS PARA TTS ==========
  const [isTTSEnabled, setIsTTSEnabled] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const speechSynthRef = useRef(null);
  const lastSpokenTextRef = useRef("");
  
  const [stats, setStats] = useState({
    fps: 0,
    cpu: 0,
    ram: 0,
    inference_time_ms: 0,
    buffer_current: 0,
    buffer_max: 30,
  });

  // ========== INICIALIZAR SPEECH SYNTHESIS ==========
  useEffect(() => {
    if ('speechSynthesis' in window) {
      speechSynthRef.current = window.speechSynthesis;
      console.log("Text-to-Speech disponible");
      
      // Listar voces disponibles (opcional, para debug)
      const loadVoices = () => {
        const voices = speechSynthRef.current.getVoices();
        console.log("Voces disponibles:", voices.filter(v => v.lang.startsWith('es')));
      };
      
      loadVoices();
      if (speechSynthRef.current.onvoiceschanged !== undefined) {
        speechSynthRef.current.onvoiceschanged = loadVoices;
      }
    } else {
      console.warn("Text-to-Speech no disponible en este navegador");
    }
    
    // Cleanup: detener cualquier speech al desmontar
    return () => {
      if (speechSynthRef.current) {
        speechSynthRef.current.cancel();
      }
    };
  }, []);

  // ========== FUNCIÓN PARA HABLAR ==========
  const speakText = (text) => {
    if (!speechSynthRef.current || !isTTSEnabled) return;
    
    // Evitar hablar el mismo texto repetidamente
    if (text === lastSpokenTextRef.current) {
      return;
    }
    
    // Cancelar cualquier speech en curso
    speechSynthRef.current.cancel();
    
    // Filtrar textos que no queremos leer
    const ignoredTexts = [
      "NO_HANDS_DETECTED",
      "LOADING_SEQUENCE",
      "BAJA_CONFIANZA",
      "Esperando detección...",
    ];
    
    if (ignoredTexts.includes(text) || text.startsWith("ERROR")) {
      return;
    }
    
    // Crear el utterance (mensaje de voz)
    const utterance = new SpeechSynthesisUtterance(text);
    
    // Configurar voz en español
    const voices = speechSynthRef.current.getVoices();
    const spanishVoice = voices.find(voice => 
      voice.lang.startsWith('es-') || voice.lang === 'es'
    );
    
    if (spanishVoice) {
      utterance.voice = spanishVoice;
    }
    
    // Configuraciones de voz
    utterance.lang = 'es-CO'; // Español de España (o 'es-MX', 'es-CO', etc.)
    utterance.rate = 1.0;     // Velocidad (0.1 - 10)
    utterance.pitch = 1.0;    // Tono (0 - 2)
    utterance.volume = 1.0;   // Volumen (0 - 1)
    
    // Eventos
    utterance.onstart = () => {
      setIsSpeaking(true);
      lastSpokenTextRef.current = text;
      console.log("Hablando:", text);
    };
    
    utterance.onend = () => {
      setIsSpeaking(false);
      console.log("Finalizado speech");
    };
    
    utterance.onerror = (event) => {
      setIsSpeaking(false);
      console.error("Error en speech:", event);
    };
    
    // Hablar
    speechSynthRef.current.speak(utterance);
  };

  // ========== TOGGLE TTS ==========
  const toggleTTS = () => {
    const newState = !isTTSEnabled;
    setIsTTSEnabled(newState);
    
    // Si se desactiva, detener cualquier speech en curso
    if (!newState && speechSynthRef.current) {
      speechSynthRef.current.cancel();
      setIsSpeaking(false);
      lastSpokenTextRef.current = "";
    }
    
    console.log(newState ? "TTS Activado" : "TTS Desactivado");
  };

  // ========== DETENER SPEECH MANUALMENTE ==========
  const stopSpeaking = () => {
    if (speechSynthRef.current) {
      speechSynthRef.current.cancel();
      setIsSpeaking(false);
    }
  };

  useEffect(() => {
    if (!videoSocket) return;

    const handleMessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "video_frame") {
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

          // Actualizar predicción
          if (data.prediction) {
            setCurrentTranslation(data.prediction);
            setConfidence(data.confidence || 0);

            // ========== HABLAR LA TRADUCCIÓN ==========
            if (
              data.confidence > 0.7 &&
              data.prediction !== "NO_HANDS_DETECTED" &&
              data.prediction !== "LOADING_SEQUENCE" &&
              data.prediction !== "BAJA_CONFIANZA" &&
              !data.prediction.startsWith("ERROR")
            ) {
              // Hablar la nueva traducción
              speakText(data.prediction);
              
              // Guardar en historial
              setTranslationsHistory((prev) => {
                // Evitar duplicados consecutivos
                if (prev.length > 0 && prev[0].text === data.prediction) {
                  return prev;
                }
                
                return [
                  {
                    text: data.prediction,
                    confidence: data.confidence,
                    timestamp: new Date().toLocaleTimeString(),
                  },
                  ...prev.slice(0, 14), // Mantener últimas 15
                ];
              });
            }
          }

          // Actualizar métricas de rendimiento
          if (data.performance) {
            setStats({
              fps: data.performance.fps || 0,
              cpu: data.performance.cpu || 0,
              ram: data.performance.ram || 0,
              inference_time_ms: data.performance.inference_time_ms || 0,
              buffer_current: data.buffer_status?.current || 0,
              buffer_max: data.buffer_status?.max || 30,
            });
          }
        }
      } catch (err) {
        console.error("Error procesando mensaje de video:", err);
      }
    };

    videoSocket.addEventListener("message", handleMessage);
    return () => videoSocket.removeEventListener("message", handleMessage);
  }, [videoSocket, isTTSEnabled]); // Agregar isTTSEnabled como dependencia

  const handleStartSession = () => {
    setIsProcessing(true);
    startSession();
  };

  const handleStopSession = () => {
    setIsProcessing(false);
    stopSession();
    stopSpeaking(); // Detener speech al detener sesión
  };

  const handleResetClassifier = () => {
    resetClassifier();
    setTranslationsHistory([]);
    setCurrentTranslation("");
    setConfidence(0);
    stopSpeaking(); // Detener speech al resetear
    lastSpokenTextRef.current = "";
  };

  const getConfidenceColor = (conf) => {
    if (conf > 0.8) return "#10b981"; // verde
    if (conf > 0.6) return "#f59e0b"; // amarillo
    return "#ef4444"; // rojo
  };

  const getPredictionStatus = (text) => {
    if (text === "NO_HANDS_DETECTED") return "sin-manos";
    if (text === "LOADING_SEQUENCE") return "cargando";
    if (text === "BAJA_CONFIANZA") return "baja-confianza";
    if (text.startsWith("ERROR")) return "error";
    return "detectado";
  };

  // Pedir estado al conectarse
  useEffect(() => {
    if (isConnected) {
      getStatus();
    }
  }, [isConnected, getStatus]);

  // Sincronizar estado de sesión
  useEffect(() => {
    if (currentSession !== null) {
      setIsProcessing(true);
    } else {
      setIsProcessing(false);
    }
  }, [currentSession]);

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
                  {isConnected ? (
                    <>
                      <Wifi size={16} className="icon-connected" />
                      <span className="status-text connected">Conectado</span>
                    </>
                  ) : (
                    <>
                      <WifiOff size={16} className="icon-disconnected" />
                      <span className="status-text disconnected">
                        Desconectado
                      </span>
                    </>
                  )}
                </div>
              </div>

              <div className="video-wrapper">
                <canvas
                  ref={videoCanvasRef}
                  width="640"
                  height="480"
                  className="video-canvas"
                />
                
                {/* Overlay con información */}
                <div className="video-overlay">
                  <div className="overlay-item fps">
                    <Zap size={14} />
                    FPS: {stats.fps?.toFixed(1) || "0"}
                  </div>
                  <div className="overlay-item buffer">
                    Buffer: {stats.buffer_current}/{stats.buffer_max}
                  </div>
                  {systemStatus?.model_info && (
                    <div className="overlay-item model">
                      <Cpu size={14} />
                      Modelo: {systemStatus.model_info.type} (
                      {systemStatus.model_info.features} features)
                    </div>
                  )}
                  
                  {/* ========== INDICADOR TTS ========== */}
                  {isTTSEnabled && (
                    <div className={`overlay-item tts ${isSpeaking ? 'speaking' : ''}`}>
                      <Volume2 size={14} />
                      {isSpeaking ? "Hablando..." : "TTS Activo"}
                    </div>
                  )}
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
                  title="Información avanzada"
                >
                  <Settings size={16} />
                </button>
              </div>

              <div className="translation-content">
                {/* Texto de predicción */}
                <div
                  className={`translation-text status-${getPredictionStatus(
                    currentTranslation
                  )}`}
                >
                  {currentTranslation || "Esperando detección..."}
                </div>

                {/* Barra de confianza */}
                {confidence > 0 && (
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
                )}

                {/* Estado de sesión */}
                {currentSession && (
                  <div className="session-info">
                    <div className="session-badge">
                      <div className="recording-indicator" />
                      <span>Sesión activa: #{currentSession}</span>
                    </div>
                  </div>
                )}

                {/* Info avanzada */}
                {showAdvancedInfo && (
                  <div className="advanced-info">
                    <h4>Métricas del Sistema</h4>
                    <div className="info-grid">
                      <div className="info-item">
                        <label>FPS:</label>
                        <span>{stats.fps?.toFixed(1) || "0"}</span>
                      </div>
                      <div className="info-item">
                        <label>Inferencia:</label>
                        <span>{stats.inference_time_ms?.toFixed(1)} ms</span>
                      </div>
                      <div className="info-item">
                        <label>CPU:</label>
                        <span>{stats.cpu?.toFixed(1) || "0"}%</span>
                      </div>
                      <div className="info-item">
                        <label>RAM:</label>
                        <span>{stats.ram?.toFixed(1) || "0"}%</span>
                      </div>
                      <div className="info-item">
                        <label>Buffer:</label>
                        <span>
                          {stats.buffer_current}/{stats.buffer_max}
                        </span>
                      </div>
                      {systemStatus?.model_info && (
                        <div className="info-item">
                          <label>Clases:</label>
                          <span>{systemStatus.model_info.classes}</span>
                        </div>
                      )}
                      <div className="info-item">
                        <label>TTS:</label>
                        <span>{isTTSEnabled ? "Activo" : "Inactivo"}</span>
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
              title={
                isProcessing
                  ? "Detener sesión de grabación"
                  : "Iniciar sesión de grabación"
              }
            >
              {isProcessing ? <Square size={16} /> : <Play size={16} />}
              {isProcessing ? "Detener Sesión" : "Iniciar Sesión"}
            </button>

            {/* ========== BOTÓN TTS ========== */}
            <button
              className={`control-btn ${isTTSEnabled ? 'tts-active' : 'secondary'}`}
              onClick={toggleTTS}
              disabled={!isConnected}
              title={isTTSEnabled ? "Desactivar lectura por voz" : "Activar lectura por voz"}
            >
              {isTTSEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
              {isTTSEnabled ? "Voz Activada" : "Activar Voz"}
            </button>

            <button
              className="control-btn secondary"
              onClick={handleResetClassifier}
              disabled={!isConnected}
              title="Reiniciar buffer del clasificador"
            >
              <RotateCcw size={16} />
              Reiniciar
            </button>

            <button
              className="control-btn secondary"
              onClick={getStatus}
              disabled={!isConnected}
              title="Obtener estado del sistema"
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
              <span className="history-count">
                {translationsHistory.length} registro
                {translationsHistory.length !== 1 ? "s" : ""}
              </span>
            </div>

            <div className="translations-list">
              {translationsHistory.length === 0 ? (
                <div className="empty-history">
                  <p>No hay traducciones recientes</p>
                  <span>Las señas detectadas aparecerán aquí</span>
                </div>
              ) : (
                translationsHistory.map((t, i) => (
                  <div key={`${t.timestamp}-${i}`} className="translation-item">
                    <div className="translation-main">
                      <span className="item-text">{t.text}</span>
                      <span
                        className="confidence-badge"
                        style={{
                          backgroundColor: getConfidenceColor(t.confidence),
                        }}
                      >
                        {Math.round(t.confidence * 100)}%
                      </span>
                    </div>
                    <div className="translation-meta">
                      <span className="timestamp">{t.timestamp}</span>
                    </div>
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