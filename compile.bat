@ECHO OFF
SETLOCAL

:: ============================================================================
::  SoupTextures Build Script
:: ============================================================================
::  This script builds the SoupTextures executable using PyInstaller,
::  then cleans up the temporary build files and folders.
:: ============================================================================

:: --- Configuration ---
:: Set the name for your application here. All other steps will use this name.
SET "APP_NAME=SoupTextures_1.7"

:: --- Pre-build Check ---
:: Ensure the main script exists before we start
IF NOT EXIST "main_gui.py" (
    ECHO ERROR: Cannot find the main script 'main_gui.py'.
    ECHO Make sure this build script is in the same directory as your Python files.
    GOTO :End
)

ECHO #########################################
ECHO #         BUILDING %APP_NAME%         #
ECHO #########################################
ECHO.

:: Run PyInstaller with all the specified options
pyinstaller --name "%APP_NAME%" --onefile --windowed --icon="soup.ico" --add-binary "texconv.exe:." --clean main_gui.py

:: Check if PyInstaller succeeded. If not, stop the script.
:: A non-zero ERRORLEVEL indicates that the previous command failed.
IF %ERRORLEVEL% NEQ 0 (
    ECHO.
    ECHO #######################################################
    ECHO #  PyInstaller failed to build the executable.        #
    ECHO #  Check the output above for errors. Aborting.       #
    ECHO #######################################################
    ECHO.
    GOTO :End
)

ECHO.
ECHO #########################################
ECHO #       CLEANING UP BUILD FILES       #
ECHO #########################################
ECHO.

:: --- Move the Executable ---
:: Move the created .exe from the 'dist' folder to the current directory.
:: The /Y flag overwrites any existing file without prompting.
ECHO Moving %APP_NAME%.exe...
IF EXIST "dist\%APP_NAME%.exe" (
    MOVE /Y "dist\%APP_NAME%.exe" .
) ELSE (
    ECHO WARNING: Could not find the executable in the 'dist' folder.
)

:: --- Delete Folders ---
:: RMDIR (or RD) removes directories.
:: /S flag removes all subdirectories and files.
:: /Q flag runs in quiet mode (no confirmation prompts).
:: We check if the folder exists first to avoid "path not found" errors.
ECHO Deleting temporary build folders...

IF EXIST "dist" (
    RMDIR /S /Q "dist"
    ECHO  - 'dist' folder removed.
)
IF EXIST "build" (
    RMDIR /S /Q "build"
    ECHO  - 'build' folder removed.
)
:: Also check for __pycache__ which is a common Python cache folder
IF EXIST "__pycache__" (
    RMDIR /S /Q "__pycache__"
    ECHO  - '__pycache__' folder removed.
)

:: --- Delete .spec File ---
:: DEL removes files.
:: /F forces deletion of read-only files.
:: /Q is quiet mode.
ECHO Deleting .spec file...
IF EXIST "%APP_NAME%.spec" (
    DEL /F /Q "%APP_NAME%.spec"
    ECHO  - '%APP_NAME%.spec' file removed.
)

ECHO.
ECHO #########################################
ECHO #           BUILD COMPLETE            #
ECHO #########################################
ECHO.
ECHO Your executable '%APP_NAME%.exe' is ready!
ECHO.


:End
ENDLOCAL
PAUSE