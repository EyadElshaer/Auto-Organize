# Auto Organizer Changelog

## v2.0.2 - Functionality Fixes and Improvements

### Bug Fixes
- Fixed issue where the application doesn't work on first start
- Fixed folder processing with commas and parentheses
- Fixed timer not starting when watching is enabled
- Added more detailed logging for file operations
- Improved directory processing to handle all tag formats
- Fixed inconsistent behavior when starting/stopping watching

### Technical Improvements
- Added immediate scan when watching is started
- Fixed signal handler warnings
- Improved error reporting for file operations
- Enhanced directory structure creation

## v1.0.3 - Stability Improvements for Windows 10/11

### Bug Fixes
- Fixed inconsistent behavior across different Windows versions (10/11)
- Improved error handling throughout the application
- Added better fallback mechanisms when features aren't available
- Enhanced system tray handling with multiple fallback options
- Fixed registry access issues on different Windows configurations
- Improved file path handling and validation
- Added timeout handling for file operations
- Enhanced subprocess handling for robocopy operations
- Added better error reporting and logging
- Fixed startup registration to work on both Windows 10 and 11
- Added proper cleanup of resources on application exit
- Improved DPI scaling for high-resolution displays
- Added global exception handler to catch and report unhandled errors
- Fixed potential file locking issues
- Added better thread safety for UI operations
- Fixed keyboard interrupt handling to prevent crashes when using Ctrl+C
- Added graceful shutdown on interruption

### New Features
- Added verbose logging option for troubleshooting
- Added configuration option to control directory processing
- Added better config file corruption handling with automatic backup
- Enhanced error messages with more detailed information
- Added fallback mechanisms for all critical operations
- Improved compatibility with different Windows environments

### Technical Improvements
- Added proper error handling for watchdog import
- Added better subprocess handling with timeouts
- Improved registry access with proper error handling
- Enhanced file system operations with better error reporting
- Added better thread synchronization
- Improved application startup and shutdown sequence
- Added better handling of system theme detection
- Enhanced keyboard interrupt handling in all critical operations
- Added signal handling for graceful termination
- Improved version refresh mechanism with better error handling
