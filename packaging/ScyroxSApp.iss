; Inno Setup kurulum tarifi. Doğrudan değil, packaging/build.py ile derleyin
; (sürüm ve klasörler oradan /D ile gelir).
;
; - Program Files'a kurulur (C:\Program Files\Scyrox S-App); kurulum ve güncellemede yönetici
;   izni (UAC) istenir. Uygulamanın kendisi normal kullanıcı olarak çalışır.
; - AppId sabit: yeni sürüm eskisinin üstüne kurulur, ikinci kopya oluşmaz.
; - Kurulum / kaldırma öncesi çalışan uygulama kapatılır.
; - Windows açılınca başlatma kurulumda değil, uygulamanın kendisinde (tanıtım ve
;   Uygulama ayarları) seçilir; kaldırınca o kayıt ve ayarlar da silinir.
; - Sessiz kurulumda (/SILENT, uygulama içi güncelleme) bitince uygulama yeniden açılır.

#ifndef AppVersion
  #error AppVersion tanımlı değil: packaging/build.py ile derleyin
#endif
#ifndef SourceDir
  #error SourceDir tanımlı değil
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif
#ifndef IconFile
  #error IconFile tanımlı değil
#endif

#define AppName "Scyrox S-App"
#define AppExe "ScyroxSApp.exe"

[Setup]
AppId={{46A46FDF-9FF6-4B08-8AE5-C65DA492A068}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=0merfguzel
AppPublisherURL=https://github.com/0merfguzel/scyrox-s-app
AppSupportURL=https://github.com/0merfguzel/scyrox-s-app/issues
AppUpdatesURL=https://github.com/0merfguzel/scyrox-s-app/releases
VersionInfoVersion={#AppVersion}
PrivilegesRequired=admin
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
DisableReadyPage=yes
UsePreviousAppDir=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
OutputDir={#OutputDir}
OutputBaseFilename=ScyroxSApp-{#AppVersion}-Setup
; Uygulamayı kendimiz kapatıyoruz (aşağıda); Windows'un "şu programlar dosyaları kullanıyor" sorusu çıkmasın
CloseApplications=no
RestartApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
#ifexist AddBackslash(CompilerPath) + "Languages\Turkish.isl"
Name: "tr"; MessagesFile: "compiler:Languages\Turkish.isl"
#endif
#ifexist AddBackslash(CompilerPath) + "Languages\German.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
#endif
#ifexist AddBackslash(CompilerPath) + "Languages\Spanish.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
#endif
#ifexist AddBackslash(CompilerPath) + "Languages\French.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
#endif
#ifexist AddBackslash(CompilerPath) + "Languages\Portuguese.isl"
Name: "pt"; MessagesFile: "compiler:Languages\Portuguese.isl"
#endif
#ifexist AddBackslash(CompilerPath) + "Languages\BrazilianPortuguese.isl"
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
#endif
#ifexist AddBackslash(CompilerPath) + "Languages\Russian.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
#endif
#ifexist AddBackslash(CompilerPath) + "Languages\Japanese.isl"
Name: "ja"; MessagesFile: "compiler:Languages\Japanese.isl"
#endif
#ifexist AddBackslash(CompilerPath) + "Languages\Korean.isl"
Name: "ko"; MessagesFile: "compiler:Languages\Korean.isl"
#endif
#ifexist AddBackslash(CompilerPath) + "Languages\ChineseSimplified.isl"
Name: "zh"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; Yeni sürümde artık olmayan kütüphaneler kalmasın
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; build.py klasöre LICENSE.txt'yi de koyar
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; Kurulum yönetici olarak çalışır; uygulama kurulumu başlatan kullanıcı olarak açılsın (yönetici değil)
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Parameters: "--lang={code:AppLanguage}"; Flags: nowait postinstall skipifsilent runasoriginaluser
; Uygulama içi güncelleme sessiz kurar; bitince uygulama kendiliğinden geri gelsin
Filename: "{app}\{#AppExe}"; Flags: nowait runasoriginaluser; Check: WizardSilent

[Code]
{ Kurulumda seçilen dil uygulamanın da dili olsun (yalnızca kurulum sonunda açılırken;
  sessiz güncelleme uygulamada seçilmiş dili değiştirmez). }
function AppLanguage(Param: String): String;
begin
  Result := ActiveLanguage();
  if Result = 'ptbr' then
    Result := 'pt';
end;

procedure CloseApp();
var
  Code: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#AppExe}', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Sleep(500);   { dosya kilitleri bırakılsın }
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  CloseApp();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  CloseApp();
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    { Windows açılınca başlatma kaydı (ve Görev Yöneticisi'nin açık/kapalı işareti) }
    RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'ScyroxSApp');
    RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run', 'ScyroxSApp');
    { Ayarlar ve hata kaydı }
    if not DelTree(ExpandConstant('{userappdata}\ScyroxSApp'), True, True, True) then
    begin
      Sleep(1500);   { kapatılan uygulamanın dosya kilidi geç bırakılmış olabilir }
      if not DelTree(ExpandConstant('{userappdata}\ScyroxSApp'), True, True, True) then
        Log('Could not delete ' + ExpandConstant('{userappdata}\ScyroxSApp'));
    end;
  end;
end;
