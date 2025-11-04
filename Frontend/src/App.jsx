import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { SocketProvider } from "./context/SocketContext";
import Header from "./components/Header/Header"
import Home from "./pages/home/Home";
import Translation from "./pages/index/Translation";
import "./App.css";

function App() {
  return (
    <SocketProvider>
      <Router>
        <div className="App">
          <Header />
          <main>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/translation" element={<Translation />} />
            </Routes>
          </main>
        </div>
      </Router>
    </SocketProvider>
  );
}

export default App;
