import axios from 'axios';
import { toast } from 'sonner';

// Configuration
const API_CONFIG = {
  baseURL: process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000',
  timeout: 30000, // 30 seconds
  retries: 3,
  retryDelay: 1000, // 1 second
  retryDelayMultiplier: 2,
};

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: API_CONFIG.baseURL,
  timeout: API_CONFIG.timeout,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
});

// Request interceptor for logging
apiClient.interceptors.request.use(
  (config) => {
    const requestId = Date.now().toString(36) + Math.random().toString(36).substr(2);
    config.metadata = { startTime: Date.now(), requestId };
    
    console.log(`[API Request ${requestId}]`, {
      method: config.method?.toUpperCase(),
      url: config.url,
      data: config.data,
      timestamp: new Date().toISOString(),
    });
    
    return config;
  },
  (error) => {
    console.error('[API Request Error]', error);
    return Promise.reject(error);
  }
);

// Response interceptor for logging and error handling
apiClient.interceptors.response.use(
  (response) => {
    const duration = Date.now() - response.config.metadata.startTime;
    const requestId = response.config.metadata.requestId;
    
    console.log(`[API Response ${requestId}]`, {
      status: response.status,
      duration: `${duration}ms`,
      data: response.data,
      timestamp: new Date().toISOString(),
    });
    
    return response;
  },
  (error) => {
    const requestId = error.config?.metadata?.requestId || 'unknown';
    const duration = error.config?.metadata?.startTime 
      ? Date.now() - error.config.metadata.startTime 
      : 0;
    
    console.error(`[API Error ${requestId}]`, {
      status: error.response?.status,
      statusText: error.response?.statusText,
      duration: `${duration}ms`,
      message: error.message,
      data: error.response?.data,
      timestamp: new Date().toISOString(),
    });
    
    return Promise.reject(error);
  }
);

// Retry logic with exponential backoff
const retryRequest = async (fn, retries = API_CONFIG.retries) => {
  let lastError;
  
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      
      // Don't retry on client errors (4xx) except for 408, 429
      const status = error.response?.status;
      if (status && status >= 400 && status < 500 && ![408, 429].includes(status)) {
        throw error;
      }
      
      // Don't retry on the last attempt
      if (attempt === retries) {
        throw error;
      }
      
      // Calculate delay with exponential backoff and jitter
      const delay = API_CONFIG.retryDelay * Math.pow(API_CONFIG.retryDelayMultiplier, attempt);
      const jitter = Math.random() * 0.1 * delay; // Add up to 10% jitter
      const totalDelay = delay + jitter;
      
      console.warn(`[API Retry] Attempt ${attempt + 1}/${retries + 1} failed, retrying in ${Math.round(totalDelay)}ms...`, {
        error: error.message,
        status: error.response?.status,
      });
      
      await new Promise(resolve => setTimeout(resolve, totalDelay));
    }
  }
  
  throw lastError;
};

// Enhanced error handling
const handleApiError = (error, context = '') => {
  const errorInfo = {
    context,
    message: error.message,
    status: error.response?.status,
    statusText: error.response?.statusText,
    data: error.response?.data,
    timestamp: new Date().toISOString(),
  };
  
  console.error('[API Error Handler]', errorInfo);
  
  // User-friendly error messages
  let userMessage = 'An unexpected error occurred. Please try again.';
  let description = error.message;
  
  if (error.code === 'NETWORK_ERROR' || !error.response) {
    userMessage = 'Network connection failed';
    description = 'Please check your internet connection and try again.';
  } else if (error.code === 'ECONNABORTED') {
    userMessage = 'Request timeout';
    description = 'The request took too long to complete. Please try again.';
  } else {
    const status = error.response?.status;
    switch (status) {
      case 400:
        userMessage = 'Invalid request';
        description = error.response?.data?.message || 'Please check your input and try again.';
        break;
      case 401:
        userMessage = 'Authentication required';
        description = 'Please log in and try again.';
        break;
      case 403:
        userMessage = 'Access denied';
        description = 'You don\'t have permission to perform this action.';
        break;
      case 404:
        userMessage = 'Service not found';
        description = 'The requested service is not available. Please check if the backend is running.';
        break;
      case 429:
        userMessage = 'Too many requests';
        description = 'Please wait a moment before trying again.';
        break;
      case 500:
        userMessage = 'Server error';
        description = 'An internal server error occurred. Please try again later.';
        break;
      case 502:
      case 503:
      case 504:
        userMessage = 'Service unavailable';
        description = 'The service is temporarily unavailable. Please try again later.';
        break;
      default:
        // Keep default userMessage and description
        break;
    }
  }
  
  // Show user-friendly toast notification
  toast.error(userMessage, {
    description,
    duration: 5000,
    action: {
      label: 'Retry',
      onClick: () => window.location.reload(),
    },
  });
  
  return {
    ...errorInfo,
    userMessage,
    description,
  };
};

// API service class
class ApiService {
  constructor() {
    this.client = apiClient;
  }
  
  // Health check
  async healthCheck() {
    return retryRequest(async () => {
      const response = await this.client.get('/');
      return response.data;
    });
  }
  
  // Pipeline validation
  async validatePipeline(nodes, edges) {
    if (!Array.isArray(nodes) || !Array.isArray(edges)) {
      throw new Error('Invalid pipeline data: nodes and edges must be arrays');
    }
    
    return retryRequest(async () => {
      const response = await this.client.post('/pipelines/parse', {
        nodes,
        edges,
      });
      return response.data;
    });
  }
  
  // Generic request method with error handling
  async request(method, url, data = null, config = {}) {
    try {
      return await retryRequest(async () => {
        const response = await this.client.request({
          method,
          url,
          data,
          ...config,
        });
        return response.data;
      });
    } catch (error) {
      const errorInfo = handleApiError(error, `${method.toUpperCase()} ${url}`);
      throw errorInfo;
    }
  }
}

// Create singleton instance
export const apiService = new ApiService();

// Export individual methods for convenience
export const healthCheck = () => apiService.healthCheck();
export const validatePipeline = (nodes, edges) => apiService.validatePipeline(nodes, edges);

// Connection status checker
export const checkConnectionStatus = async () => {
  try {
    await healthCheck();
    return { connected: true, error: null };
  } catch (error) {
    return { 
      connected: false, 
      error: error.userMessage || 'Connection failed' 
    };
  }
};

export default apiService;
