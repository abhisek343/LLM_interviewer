// Error logging utility
const errorLogger = {
  logUnauthorizedAccess: (user, attemptedRoute, requiredRole) => {
    const timestamp = new Date().toISOString();
    const logEntry = {
      timestamp,
      user: user ? {
        id: user.id,
        username: user.username,
        role: user.role,
      } : 'anonymous',
      attemptedRoute,
      requiredRole,
      type: 'unauthorized_access',
    };

    // Log to console in development
    if (process.env.NODE_ENV === 'development') {
      console.warn('Unauthorized access attempt:', logEntry);
    }

    // In production, you would typically send this to a logging service
    // For example:
    // fetch('/api/logs', {
    //   method: 'POST',
    //   headers: {
    //     'Content-Type': 'application/json',
    //   },
    //   body: JSON.stringify(logEntry),
    // });
  },

  logError: (error, context) => {
    const timestamp = new Date().toISOString();
    const logEntry = {
      timestamp,
      error: {
        message: error.message,
        stack: error.stack,
      },
      context,
      type: 'error',
    };

    // Log to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('Error occurred:', logEntry);
    }

    // In production, you would typically send this to a logging service
    // For example:
    // fetch('/api/logs', {
    //   method: 'POST',
    //   headers: {
    //     'Content-Type': 'application/json',
    //   },
    //   body: JSON.stringify(logEntry),
    // });
  },
};

export default errorLogger; 