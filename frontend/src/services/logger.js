// Logging levels
const LOG_LEVELS = {
  ERROR: 0,
  WARN: 1,
  INFO: 2,
  DEBUG: 3,
};

const LOG_LEVEL_NAMES = {
  0: 'ERROR',
  1: 'WARN',
  2: 'INFO',
  3: 'DEBUG',
};

// Configuration
const LOGGER_CONFIG = {
  level: process.env.NODE_ENV === 'development' ? LOG_LEVELS.DEBUG : LOG_LEVELS.INFO,
  enableConsole: true,
  enableStorage: true,
  maxStoredLogs: 1000,
  enablePerformanceTracking: true,
};

class Logger {
  constructor(config = LOGGER_CONFIG) {
    this.config = config;
    this.logs = this.loadStoredLogs();
    this.sessionId = this.generateSessionId();
    this.startTime = Date.now();
    
    // Performance tracking
    this.performanceMarks = new Map();
    this.performanceMetrics = {
      pageLoadTime: 0,
      apiCalls: [],
      componentRenders: [],
      userInteractions: [],
    };
    
    // Initialize performance tracking
    this.initPerformanceTracking();
    
    // Log session start
    this.info('Logger initialized', {
      sessionId: this.sessionId,
      environment: process.env.NODE_ENV,
      userAgent: navigator.userAgent,
      url: window.location.href,
    });
  }
  
  generateSessionId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
  }
  
  initPerformanceTracking() {
    if (!this.config.enablePerformanceTracking) return;
    
    // Track page load time
    if (window.performance && window.performance.timing) {
      window.addEventListener('load', () => {
        const timing = window.performance.timing;
        this.performanceMetrics.pageLoadTime = timing.loadEventEnd - timing.navigationStart;
        this.info('Page load completed', {
          pageLoadTime: this.performanceMetrics.pageLoadTime,
          domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
          firstPaint: timing.loadEventStart - timing.navigationStart,
        });
      });
    }
    
    // Track unhandled errors
    window.addEventListener('error', (event) => {
      this.error('Unhandled error', {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        stack: event.error?.stack,
      });
    });
    
    // Track unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      this.error('Unhandled promise rejection', {
        reason: event.reason,
        promise: event.promise,
      });
    });
  }
  
  createLogEntry(level, message, data = {}, category = 'general') {
    return {
      id: Date.now().toString(36) + Math.random().toString(36).substr(2),
      timestamp: new Date().toISOString(),
      sessionId: this.sessionId,
      level: LOG_LEVEL_NAMES[level],
      category,
      message,
      data,
      url: window.location.href,
      userAgent: navigator.userAgent,
      sessionTime: Date.now() - this.startTime,
    };
  }
  
  shouldLog(level) {
    return level <= this.config.level;
  }
  
  log(level, message, data = {}, category = 'general') {
    if (!this.shouldLog(level)) return;
    
    const logEntry = this.createLogEntry(level, message, data, category);
    
    // Console logging
    if (this.config.enableConsole) {
      const consoleMethod = level === LOG_LEVELS.ERROR ? 'error' 
        : level === LOG_LEVELS.WARN ? 'warn' 
        : level === LOG_LEVELS.DEBUG ? 'debug' 
        : 'log';
      
      console[consoleMethod](`[${logEntry.level}] ${logEntry.message}`, {
        category: logEntry.category,
        data: logEntry.data,
        timestamp: logEntry.timestamp,
      });
    }
    
    // Store logs
    if (this.config.enableStorage) {
      this.storeLog(logEntry);
    }
    
    return logEntry;
  }
  
  error(message, data = {}, category = 'error') {
    return this.log(LOG_LEVELS.ERROR, message, data, category);
  }
  
  warn(message, data = {}, category = 'warning') {
    return this.log(LOG_LEVELS.WARN, message, data, category);
  }
  
  info(message, data = {}, category = 'info') {
    return this.log(LOG_LEVELS.INFO, message, data, category);
  }
  
  debug(message, data = {}, category = 'debug') {
    return this.log(LOG_LEVELS.DEBUG, message, data, category);
  }
  
  // Specialized logging methods
  apiCall(method, url, data = {}, duration = null) {
    const entry = {
      method,
      url,
      data,
      duration,
      timestamp: Date.now(),
    };
    
    this.performanceMetrics.apiCalls.push(entry);
    
    return this.info(`API ${method.toUpperCase()} ${url}`, entry, 'api');
  }
  
  componentRender(componentName, props = {}, duration = null) {
    const entry = {
      componentName,
      props,
      duration,
      timestamp: Date.now(),
    };
    
    this.performanceMetrics.componentRenders.push(entry);
    
    return this.debug(`Component render: ${componentName}`, entry, 'render');
  }
  
  userInteraction(action, target = null, data = {}) {
    const entry = {
      action,
      target,
      data,
      timestamp: Date.now(),
    };
    
    this.performanceMetrics.userInteractions.push(entry);
    
    return this.info(`User interaction: ${action}`, entry, 'interaction');
  }
  
  performance(name, data = {}) {
    return this.info(`Performance: ${name}`, data, 'performance');
  }
  
  // Performance measurement utilities
  startTimer(name) {
    this.performanceMarks.set(name, Date.now());
  }
  
  endTimer(name, data = {}) {
    const startTime = this.performanceMarks.get(name);
    if (!startTime) {
      this.warn(`Timer '${name}' not found`);
      return null;
    }
    
    const duration = Date.now() - startTime;
    this.performanceMarks.delete(name);
    
    this.performance(`Timer: ${name}`, {
      duration,
      ...data,
    });
    
    return duration;
  }
  
  // Storage management
  storeLog(logEntry) {
    try {
      this.logs.push(logEntry);
      
      // Trim logs if too many
      if (this.logs.length > this.config.maxStoredLogs) {
        this.logs = this.logs.slice(-this.config.maxStoredLogs);
      }
      
      // Store in localStorage (with size limit)
      const logsString = JSON.stringify(this.logs);
      if (logsString.length < 5 * 1024 * 1024) { // 5MB limit
        localStorage.setItem('vectorshift_logs', logsString);
      }
    } catch (error) {
      console.error('Failed to store log:', error);
    }
  }
  
  loadStoredLogs() {
    try {
      const stored = localStorage.getItem('vectorshift_logs');
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('Failed to load stored logs:', error);
      return [];
    }
  }
  
  // Log retrieval and analysis
  getLogs(filters = {}) {
    let filteredLogs = [...this.logs];
    
    if (filters.level) {
      filteredLogs = filteredLogs.filter(log => log.level === filters.level);
    }
    
    if (filters.category) {
      filteredLogs = filteredLogs.filter(log => log.category === filters.category);
    }
    
    if (filters.sessionId) {
      filteredLogs = filteredLogs.filter(log => log.sessionId === filters.sessionId);
    }
    
    if (filters.since) {
      const sinceTime = new Date(filters.since).getTime();
      filteredLogs = filteredLogs.filter(log => new Date(log.timestamp).getTime() >= sinceTime);
    }
    
    return filteredLogs;
  }
  
  getPerformanceMetrics() {
    return {
      ...this.performanceMetrics,
      sessionDuration: Date.now() - this.startTime,
      totalLogs: this.logs.length,
      errorCount: this.logs.filter(log => log.level === 'ERROR').length,
      warningCount: this.logs.filter(log => log.level === 'WARN').length,
    };
  }
  
  exportLogs() {
    const exportData = {
      sessionId: this.sessionId,
      exportTime: new Date().toISOString(),
      config: this.config,
      logs: this.logs,
      performanceMetrics: this.getPerformanceMetrics(),
    };
    
    const dataStr = JSON.stringify(exportData, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `vectorshift-logs-${this.sessionId}.json`;
    link.click();
    
    URL.revokeObjectURL(url);
  }
  
  clearLogs() {
    this.logs = [];
    localStorage.removeItem('vectorshift_logs');
    this.info('Logs cleared');
  }
}

// Create singleton instance
export const logger = new Logger();

// Export convenience methods
export const logError = (message, data, category) => logger.error(message, data, category);
export const logWarn = (message, data, category) => logger.warn(message, data, category);
export const logInfo = (message, data, category) => logger.info(message, data, category);
export const logDebug = (message, data, category) => logger.debug(message, data, category);
export const logApiCall = (method, url, data, duration) => logger.apiCall(method, url, data, duration);
export const logComponentRender = (name, props, duration) => logger.componentRender(name, props, duration);
export const logUserInteraction = (action, target, data) => logger.userInteraction(action, target, data);
export const logPerformance = (name, data) => logger.performance(name, data);

export default logger;
