// src/pages/Translation.js (Versión priorizada)
import React, { useEffect, useRef, useState } from 'react';
import { useSocket } from '../../context/SocketContext';
import { Play, Square, RotateCcw, Camera, Activity, Zap, Settings } from 'lucide-react';
import './Translation.css';

const Translation = () => {
  const { videoSocket, isConnected, systemStatus, sendControlCommand } = useSocket();
  const videoCanvasRef = useRef(null);
  const [currentTranslation, setCurrentTranslation] = useState('');
  const [confidence, setConfidence] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [translationsHistory, setTranslationsHistory] = useState([]);
  const [cameraInfo, setCameraInfo] = useState({});
  const [showAdvancedInfo, setShowAdvancedInfo] = useState(false);
  const [stats, setStats] = useState({
    fps: 0,
    processingTime: 0,
    framesProcessed: 0
  });

  useEffect(() => {
    if (!videoSocket) return;

    const handleMessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'video_frame') {
          // Procesar frame de video
          if (data.frame && videoCanvasRef.current) {
            const img = new Image();
            img.onload = () => {
              const ctx = videoCanvasRef.current.getContext('2d');
              ctx.drawImage(img, 0, 0, videoCanvasRef.current.width, videoCanvasRef.current.height);
            };
            img.src = data.frame;
          }

          // Actualizar predicción
          if (data.prediction) {
            setCurrentTranslation(data.prediction);
            setConfidence(data.confidence);

            // Añadir a historial si la confianza es alta
            if (data.confidence > 0.7 && data.prediction !== 'NO_HANDS_DETECTED') {
              setTranslationsHistory(prev => [
                {
                  text: data.prediction,
                  confidence: data.confidence,
                  timestamp: new Date().toLocaleTimeString(),
                  saved: data.translation_saved || false
                },
                ...prev.slice(0, 9) // Mantener solo últimas 10
              ]);
            }
          }

          // Actualizar información de cámara
          if (data.camera_info) {
            setCameraInfo(data.camera_info);
          }
        }
      } catch (error) {
        console.error('Error processing message:', error);
      }
    };

    videoSocket.addEventListener('message', handleMessage);

    return () => {
      videoSocket.removeEventListener('message', handleMessage);
    };
  }, [videoSocket]);

  const handleStartSession = () => {
    setIsProcessing(true);
  };

  const handleStopSession = () => {
    setIsProcessing(false);
  };

  const handleResetClassifier = () => {
    sendControlCommand('reset_classifier');
    setTranslationsHistory([]);
    setCurrentTranslation('');
    setConfidence(0);
  };

  const handleGetStatus = () => {
    sendControlCommand('get_status');
  };

  const getConfidenceColor = (conf) => {
    if (conf > 0.8) return '#10b981'; // Verde
    if (conf > 0.6) return '#f59e0b'; // Amarillo
    return '#ef4444'; // Rojo
  };

  // Solicitar estado al cargar el componente
  useEffect(() => {
    if (isConnected) {
      handleGetStatus();
    }
  }, [isConnected]);

  return (
    <div className="translation-page">
      <div className="translation-layout">
        
        {/* Sección Principal: Video y Traducción en Misma Altura */}
        <div className="main-display">
          
          {/* Video en Tiempo Real */}
          <div className="video-section">
            <div className="video-container">
              <div className="video-header">
                <Camera size={20} />
                <h2>Video en Tiempo Real</h2>
                <div className="connection-badge">
                  <div className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`} />
                  {isConnected ? 'Conectado' : 'Desconectado'}
                </div>
              </div>
              
              <div className="video-wrapper">
                <canvas 
                  ref={videoCanvasRef}
                  width="640"
                  height="480"
                  className="video-canvas"
                />
                
                {/* Overlay de información */}
                <div className="video-overlay">
                  <div className="overlay-item fps">
                    FPS: {stats.fps?.toFixed(1) || '0'}
                  </div>
                  <div className="overlay-item camera">
                    {cameraInfo.name || 'Cámara no detectada'}
                  </div>
                  {cameraInfo.is_simulated && (
                    <div className="overlay-item simulation">
                      Modo Simulación
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Traducción Actual - Misma altura que el video */}
          <div className="translation-section">
            <div className="current-translation">
              <div className="translation-header">
                <Activity size={20} />
                <h2>Traducción Actual</h2>
                <button 
                  className="info-toggle"
                  onClick={() => setShowAdvancedInfo(!showAdvancedInfo)}
                  title="Mostrar información avanzada"
                >
                  <Settings size={16} />
                </button>
              </div>
              
              <div className="translation-content">
                <div className="translation-text">
                  {currentTranslation || 'Esperando detección...'}
                </div>
                
                <div className="confidence-section">
                  <div className="confidence-bar">
                    <div 
                      className="confidence-fill"
                      style={{ 
                        width: `${confidence * 100}%`,
                        backgroundColor: getConfidenceColor(confidence)
                      }}
                    />
                  </div>
                  <span className="confidence-value">
                    {Math.round(confidence * 100)}% de confianza
                  </span>
                </div>

                {/* Indicadores de Estado Básicos */}
                <div className="status-indicators">
                  <div className="status-item">
                    <Zap size={16} />
                    <span>Estado: {isConnected ? 'Conectado' : 'Desconectado'}</span>
                  </div>
                  {systemStatus.camera_status && (
                    <div className="status-item">
                      <Camera size={16} />
                      <span>Cámara: {systemStatus.camera_status.name}</span>
                    </div>
                  )}
                </div>

                {/* Información Avanzada (Colapsable) */}
                {showAdvancedInfo && (
                  <div className="advanced-info">
                    <div className="info-grid">
                      <div className="info-item">
                        <label>FPS:</label>
                        <span>{systemStatus.camera_status?.fps?.toFixed(1) || '0'}</span>
                      </div>
                      <div className="info-item">
                        <label>Resolución:</label>
                        <span>{systemStatus.camera_status?.actual_width || 0}x{systemStatus.camera_status?.actual_height || 0}</span>
                      </div>
                      <div className="info-item">
                        <label>Frames Procesados:</label>
                        <span>{stats.framesProcessed}</span>
                      </div>
                      <div className="info-item">
                        <label>Tiempo Procesamiento:</label>
                        <span>{(stats.processingTime * 1000).toFixed(1)}ms</span>
                      </div>
                    </div>

                    {/* Información de Distancia (Simulada) */}
                    {systemStatus.distance && (
                      <div className="distance-info">
                        <h4>Datos de Distancia</h4>
                        <div className="distance-display">
                          <div className="distance-value">
                            {systemStatus.distance.distance} cm
                          </div>
                          <div className={`distance-status ${systemStatus.distance.status.toLowerCase()}`}>
                            {systemStatus.distance.status}
                          </div>
                        </div>
                        {systemStatus.distance.is_simulated && (
                          <div className="simulation-notice">
                            ⚠️ Datos de distancia simulados
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Controles - Debajo del video y traducción */}
        <div className="controls-section">
          <div className="video-controls">
            <button 
              className={`control-btn ${isProcessing ? 'stop' : 'start'}`}
              onClick={isProcessing ? handleStopSession : handleStartSession}
              disabled={!isConnected}
            >
              {isProcessing ? <Square size={16} /> : <Play size={16} />}
              {isProcessing ? 'Detener Procesamiento' : 'Comenzar Procesamiento'}
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
              Actualizar Estado
            </button>
          </div>
        </div>

        {/* Historial de Traducciones - Parte Inferior */}
        <div className="history-section">
          <div className="history-container">
            <div className="history-header">
              <h3>Historial de Traducciones</h3>
              <span className="history-count">{translationsHistory.length} traducciones</span>
            </div>
            
            <div className="translations-list">
              {translationsHistory.length === 0 ? (
                <div className="empty-history">
                  <p>No hay traducciones recientes</p>
                  <span>Las traducciones aparecerán aquí cuando se detecten señas con alta confianza</span>
                </div>
              ) : (
                translationsHistory.map((translation, index) => (
                  <div key={index} className="translation-item">
                    <div className="translation-main">
                      <div className="translation-text">
                        {translation.text}
                      </div>
                      <div 
                        className="confidence-badge"
                        style={{ backgroundColor: getConfidenceColor(translation.confidence) }}
                      >
                        {Math.round(translation.confidence * 100)}%
                      </div>
                    </div>
                    <div className="translation-meta">
                      <span className="timestamp">{translation.timestamp}</span>
                      {translation.saved && (
                        <span className="saved-badge" title="Guardado en base de datos">💾</span>
                      )}
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