import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { 
      hasError: false, 
      error: null, 
      errorInfo: null,
      errorId: null 
    };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { 
      hasError: true,
      errorId: Date.now().toString(36) + Math.random().toString(36).substr(2)
    };
  }

  componentDidCatch(error, errorInfo) {
    // Log error details for debugging
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    
    this.setState({
      error: error,
      errorInfo: errorInfo
    });

    // In production, you might want to log this to an error reporting service
    this.logErrorToService(error, errorInfo);
  }

  logErrorToService = (error, errorInfo) => {
    // Log error with timestamp and user agent for debugging
    const errorLog = {
      timestamp: new Date().toISOString(),
      error: error.toString(),
      errorInfo: errorInfo.componentStack,
      userAgent: navigator.userAgent,
      url: window.location.href,
      errorId: this.state.errorId
    };
    
    console.error('Error logged:', errorLog);
    
    // In production, send to error monitoring service like Sentry
    // Example: Sentry.captureException(error, { extra: errorLog });
  };

  handleReload = () => {
    window.location.reload();
  };

  handleReset = () => {
    this.setState({ 
      hasError: false, 
      error: null, 
      errorInfo: null,
      errorId: null 
    });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
          <Card className="max-w-2xl w-full p-8 text-center">
            <div className="flex flex-col items-center space-y-6">
              <AlertCircle className="h-16 w-16 text-red-500" />
              
              <div className="space-y-2">
                <h1 className="text-2xl font-bold text-gray-900">
                  Something went wrong
                </h1>
                <p className="text-gray-600">
                  We've encountered an unexpected error. This has been logged for our team to investigate.
                </p>
              </div>

              {this.state.errorId && (
                <div className="bg-gray-100 p-3 rounded text-sm text-gray-700">
                  <strong>Error ID:</strong> {this.state.errorId}
                </div>
              )}

              <div className="flex space-x-4">
                <Button onClick={this.handleReset} variant="outline">
                  Try Again
                </Button>
                <Button onClick={this.handleReload}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Reload Page
                </Button>
              </div>

              {process.env.NODE_ENV === 'development' && this.state.error && (
                <details className="mt-6 w-full text-left">
                  <summary className="cursor-pointer text-sm font-medium text-gray-700 mb-2">
                    Development Error Details
                  </summary>
                  <div className="bg-red-50 border border-red-200 rounded p-4 text-sm font-mono overflow-auto max-h-64">
                    <div className="text-red-800 mb-2">
                      <strong>Error:</strong> {this.state.error.toString()}
                    </div>
                    <div className="text-red-700">
                      <strong>Component Stack:</strong>
                      <pre className="mt-1 whitespace-pre-wrap">
                        {this.state.errorInfo?.componentStack}
                      </pre>
                    </div>
                  </div>
                </details>
              )}
            </div>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
