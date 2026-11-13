[Setup]
AppName=Cobo v2
AppVersion=2.0
DefaultDirName={autopf}\Cobo
DefaultGroupName=Cobo
OutputDir=.\Output
OutputBaseFilename=Cobo_Setup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\Cobo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\Cobo"; Filename: "{app}\Cobo.exe"

[Run]
Filename: "winget"; Parameters: "install -e --id OpenJS.NodeJS --accept-source-agreements --accept-package-agreements"; StatusMsg: "Installing Node.js for background processing..."; Flags: runhidden waituntilterminated
Filename: "{cmd}"; Parameters: "/c npm install -g @anthropic-ai/claude-code"; StatusMsg: "Installing Claude CLI tool..."; Flags: runhidden waituntilterminated
