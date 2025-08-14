#include <iostream>
#include <string>
#include <vector>
#include <cstdlib>
#include <windows.h>
#include <shlwapi.h>


#pragma comment(lib, "shlwapi.lib")


std::string GetCurrentDir() {
    char path[MAX_PATH];
    GetModuleFileNameA(NULL, path, MAX_PATH);
    PathRemoveFileSpecA(path);
    return std::string(path);
}


void RunProcess(
    const std::string &configPath
) {
    std::string currentDir = GetCurrentDir();

    std::string resourceDir = currentDir; // For simplicity, same as currentDir (no MEIPASS equivalent)

    std::string clientDir = resourceDir + "\\" + "client";

    std::string clientFile;
    clientFile = clientDir + "\\src\\main.py";

    std::string command = "python \"" + clientFile + "\"";
    command += " --configPath \"" + configPath + "\"";

    //std::cout << "Executing: " << command << std::endl;

    STARTUPINFOA si = {sizeof(STARTUPINFOA)};
    PROCESS_INFORMATION pi;
    bool isCreationSucceeded = CreateProcessA(
        NULL,
        (LPSTR)command.c_str(),
        NULL,
        NULL,
        FALSE,
        CREATE_NO_WINDOW,
        NULL,
        clientDir.c_str(),
        &si,
        &pi
    );
    if (!isCreationSucceeded) {
        DWORD error = GetLastError();
        std::cerr << "CreateProcess failed (" << error << ")" << std::endl;
        return;
    }

    // Don't wait
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
}


// Run
int main() {
    std::string currentDir = GetCurrentDir();

    RunProcess(
        currentDir + "\\config.json"
    );

    return 0;
}