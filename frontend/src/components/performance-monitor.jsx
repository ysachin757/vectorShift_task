import React, { useEffect, useState, useCallback } from 'react';
import { Monitor, Activity, AlertTriangle, TrendingUp } from 'lucide-react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { useStore } from './store';
import { logger } from '../services/logger';

// Performance thresholds (moved outside component to avoid dependency issues)
const PERFORMANCE_THRESHOLDS = {
  MAX_NODES: 100,
  MAX_EDGES: 200,
  MIN_FPS: 30,
  MAX_RENDER_TIME: 16, // ~60fps
  MEMORY_WARNING: 50 * 1024 * 1024, // 50MB
};

const PerformanceMonitor = () => {
  const [performanceData, setPerformanceData] = useState({
    renderTime: 0,
    nodeCount: 0,
    edgeCount: 0,
    memoryUsage: 0,
    fps: 0,
    isLagging: false,
  });
  
  const [isVisible, setIsVisible] = useState(false);
  const nodes = useStore((state) => state.nodes);
  const edges = useStore((state) => state.edges);
  
  // Performance thresholds
  const PERFORMANCE_THRESHOLDS = {
    MAX_NODES: 100,
    MAX_EDGES: 200,
    MIN_FPS: 30,
    MAX_RENDER_TIME: 16, // ~60fps
    MEMORY_WARNING: 50 * 1024 * 1024, // 50MB
  };
  
  // FPS monitoring
  const [lastTime, setLastTime] = useState(performance.now());
  
  const measureFPS = useCallback(() => {
    let frameCount = 0;
    const now = performance.now();
    
    frameCount++;
    
    if (now - lastTime >= 1000) { // Update every second
      const fps = Math.round((frameCount * 1000) / (now - lastTime));
      setPerformanceData(prev => ({ ...prev, fps }));
      setLastTime(now);
      frameCount = 0;
    }
    
    requestAnimationFrame(measureFPS);
  }, [lastTime]);
  
  // Memory usage monitoring
  const measureMemoryUsage = useCallback(() => {
    if (performance.memory) {
      const memoryUsage = performance.memory.usedJSHeapSize;
      setPerformanceData(prev => ({ ...prev, memoryUsage }));
    }
  }, []);
  
  // Render time monitoring
  const measureRenderTime = useCallback(() => {
    const startTime = performance.now();
    
    // Use setTimeout to measure after render
    setTimeout(() => {
      const endTime = performance.now();
      const renderTime = endTime - startTime;
      
      setPerformanceData(prev => ({
        ...prev,
        renderTime,
        isLagging: renderTime > PERFORMANCE_THRESHOLDS.MAX_RENDER_TIME,
      }));
      
      if (renderTime > PERFORMANCE_THRESHOLDS.MAX_RENDER_TIME) {
        logger.warn('Slow render detected', {
          renderTime,
          nodeCount: nodes.length,
          edgeCount: edges.length,
        }, 'performance');
      }
    }, 0);
  }, [nodes.length, edges.length]);
  
  // Pipeline complexity analysis
  const analyzeComplexity = useCallback(() => {
    const nodeCount = nodes.length;
    const edgeCount = edges.length;
    
    setPerformanceData(prev => ({
      ...prev,
      nodeCount,
      edgeCount,
    }));
    
    // Check for performance warnings
    const warnings = [];
    
    if (nodeCount > PERFORMANCE_THRESHOLDS.MAX_NODES) {
      warnings.push(`High node count: ${nodeCount} (recommended: <${PERFORMANCE_THRESHOLDS.MAX_NODES})`);
    }
    
    if (edgeCount > PERFORMANCE_THRESHOLDS.MAX_EDGES) {
      warnings.push(`High edge count: ${edgeCount} (recommended: <${PERFORMANCE_THRESHOLDS.MAX_EDGES})`);
    }
    
    if (warnings.length > 0) {
      logger.warn('Performance warnings detected', {
        warnings,
        nodeCount,
        edgeCount,
      }, 'performance');
    }
    
    // Log performance metrics
    logger.performance('Pipeline complexity analyzed', {
      nodeCount,
      edgeCount,
      complexity: nodeCount + edgeCount * 2, // Simple complexity metric
    });
  }, [nodes.length, edges.length]);
  
  // Performance optimization suggestions
  const getOptimizationSuggestions = () => {
    const suggestions = [];
    
    if (performanceData.nodeCount > PERFORMANCE_THRESHOLDS.MAX_NODES) {
      suggestions.push('Consider grouping nodes into sub-pipelines');
      suggestions.push('Use node virtualization for large pipelines');
    }
    
    if (performanceData.edgeCount > PERFORMANCE_THRESHOLDS.MAX_EDGES) {
      suggestions.push('Simplify complex connections');
      suggestions.push('Consider using composite nodes');
    }
    
    if (performanceData.fps < PERFORMANCE_THRESHOLDS.MIN_FPS) {
      suggestions.push('Reduce animation complexity');
      suggestions.push('Disable real-time validation for large pipelines');
    }
    
    if (performanceData.memoryUsage > PERFORMANCE_THRESHOLDS.MEMORY_WARNING) {
      suggestions.push('Check for memory leaks');
      suggestions.push('Clear unnecessary data from nodes');
    }
    
    return suggestions;
  };
  
  // Effects
  useEffect(() => {
    measureRenderTime();
    analyzeComplexity();
  }, [measureRenderTime, analyzeComplexity]);
  
  useEffect(() => {
    measureMemoryUsage();
    const interval = setInterval(measureMemoryUsage, 5000); // Every 5 seconds
    return () => clearInterval(interval);
  }, [measureMemoryUsage]);
  
  useEffect(() => {
    const animation = requestAnimationFrame(measureFPS);
    return () => cancelAnimationFrame(animation);
  }, [measureFPS]);
  
  // Auto-show when performance issues detected
  useEffect(() => {
    const hasIssues = 
      performanceData.isLagging ||
      performanceData.fps < PERFORMANCE_THRESHOLDS.MIN_FPS ||
      performanceData.nodeCount > PERFORMANCE_THRESHOLDS.MAX_NODES ||
      performanceData.edgeCount > PERFORMANCE_THRESHOLDS.MAX_EDGES;
    
    if (hasIssues && !isVisible) {
      setIsVisible(true);
    }
  }, [performanceData, isVisible]);
  
  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };
  
  const getPerformanceStatus = () => {
    if (performanceData.isLagging || performanceData.fps < PERFORMANCE_THRESHOLDS.MIN_FPS) {
      return { status: 'poor', color: 'text-red-500', icon: AlertTriangle };
    }
    
    if (performanceData.nodeCount > PERFORMANCE_THRESHOLDS.MAX_NODES * 0.8 ||
        performanceData.edgeCount > PERFORMANCE_THRESHOLDS.MAX_EDGES * 0.8) {
      return { status: 'warning', color: 'text-yellow-500', icon: TrendingUp };
    }
    
    return { status: 'good', color: 'text-green-500', icon: Activity };
  };
  
  if (!isVisible && process.env.NODE_ENV !== 'development') {
    return null;
  }
  
  const { color, icon: StatusIcon } = getPerformanceStatus();
  const suggestions = getOptimizationSuggestions();
  
  return (
    <div className="fixed bottom-4 right-4 z-50">
      {!isVisible ? (
        <Button
          variant="outline"
          size="sm"
          onClick={() => setIsVisible(true)}
          className="bg-white shadow-lg"
        >
          <Monitor className="h-4 w-4" />
        </Button>
      ) : (
        <Card className="w-80 p-4 bg-white shadow-lg">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2">
              <Monitor className="h-4 w-4" />
              <span className="font-medium text-sm">Performance Monitor</span>
            </div>
            <div className="flex items-center space-x-2">
              <StatusIcon className={`h-4 w-4 ${color}`} />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsVisible(false)}
                className="h-6 w-6 p-0"
              >
                ×
              </Button>
            </div>
          </div>
          
          <div className="space-y-2 text-xs">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="text-gray-600">Nodes:</span>
                <span className={`ml-1 font-mono ${performanceData.nodeCount > PERFORMANCE_THRESHOLDS.MAX_NODES ? 'text-red-500' : ''}`}>
                  {performanceData.nodeCount}
                </span>
              </div>
              <div>
                <span className="text-gray-600">Edges:</span>
                <span className={`ml-1 font-mono ${performanceData.edgeCount > PERFORMANCE_THRESHOLDS.MAX_EDGES ? 'text-red-500' : ''}`}>
                  {performanceData.edgeCount}
                </span>
              </div>
              <div>
                <span className="text-gray-600">FPS:</span>
                <span className={`ml-1 font-mono ${performanceData.fps < PERFORMANCE_THRESHOLDS.MIN_FPS ? 'text-red-500' : ''}`}>
                  {performanceData.fps}
                </span>
              </div>
              <div>
                <span className="text-gray-600">Render:</span>
                <span className={`ml-1 font-mono ${performanceData.isLagging ? 'text-red-500' : ''}`}>
                  {performanceData.renderTime.toFixed(1)}ms
                </span>
              </div>
            </div>
            
            {performance.memory && (
              <div>
                <span className="text-gray-600">Memory:</span>
                <span className={`ml-1 font-mono ${performanceData.memoryUsage > PERFORMANCE_THRESHOLDS.MEMORY_WARNING ? 'text-red-500' : ''}`}>
                  {formatBytes(performanceData.memoryUsage)}
                </span>
              </div>
            )}
            
            {suggestions.length > 0 && (
              <div className="mt-3 pt-2 border-t">
                <div className="text-gray-600 mb-1">Optimization suggestions:</div>
                <ul className="text-xs space-y-1">
                  {suggestions.slice(0, 3).map((suggestion, index) => (
                    <li key={index} className="text-gray-700">
                      • {suggestion}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            <div className="flex space-x-2 mt-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => logger.exportLogs()}
                className="text-xs h-6"
              >
                Export Logs
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  logger.clearLogs();
                  logger.info('Performance monitor reset');
                }}
                className="text-xs h-6"
              >
                Reset
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
};

export default PerformanceMonitor;
