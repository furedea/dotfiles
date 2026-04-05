{
  pkgs,
  config,
  username,
  ...
}:
{
  environment.systemPackages = [ pkgs.vim ];

  nix.settings.experimental-features = "nix-command flakes";

  system = {
    configurationRevision = null;
    stateVersion = 6;
    primaryUser = username;
  };

  nixpkgs.hostPlatform = "aarch64-darwin";

  # Required for home-manager to resolve home directory.
  users.users.${username}.home = "/Users/${username}";

  time.timeZone = "Asia/Tokyo";

  # ──────────────────────────────────────────────────────
  # macOS system defaults
  # ──────────────────────────────────────────────────────
  system.defaults = {
    # ────────── Keyboard ──────────
    NSGlobalDomain = {
      KeyRepeat = 2; # fastest
      InitialKeyRepeat = 15; # fastest
      "com.apple.keyboard.fnState" = true; # F1-F12 as standard function keys

      # ────────── Text input ──────────
      NSAutomaticCapitalizationEnabled = false;
      NSAutomaticSpellingCorrectionEnabled = false;
      NSAutomaticQuoteSubstitutionEnabled = false;
      NSAutomaticDashSubstitutionEnabled = false;
      NSAutomaticPeriodSubstitutionEnabled = false;

      # ────────── Appearance ──────────
      AppleInterfaceStyle = "Dark";
      AppleShowAllExtensions = true;
      AppleShowScrollBars = "Always";

      # ────────── Trackpad cursor speed ──────────
      "com.apple.trackpad.scaling" = 3.0;
    };

    # ────────── Finder ──────────
    finder = {
      AppleShowAllFiles = true;
      ShowPathbar = true;
      ShowStatusBar = true;
      FXPreferredViewStyle = "clmv"; # column view
      FXEnableExtensionChangeWarning = false;
      ShowExternalHardDrivesOnDesktop = true;
      ShowHardDrivesOnDesktop = false;
      ShowMountedServersOnDesktop = true;
      ShowRemovableMediaOnDesktop = true;
      _FXSortFoldersFirst = true;
      QuitMenuItem = true;
    };

    # ────────── Dock ──────────
    dock = {
      autohide = true;
      orientation = "bottom";
      tilesize = 128;
      magnification = false;
      largesize = 16;
      show-recents = false;
      minimize-to-application = true;
      mineffect = "scale";
      launchanim = true;
      expose-group-apps = true;
      mru-spaces = true;
      show-process-indicators = true;
      showMissionControlGestureEnabled = true;
      showAppExposeGestureEnabled = false;
      showDesktopGestureEnabled = false;
      showLaunchpadGestureEnabled = false;

      # ────────── Hot corners ──────────
      # 4=Desktop, 12=Notification Center, 13=Lock Screen, 14=Quick Note
      wvous-tl-corner = 4;
      wvous-tr-corner = 12;
      wvous-bl-corner = 13;
      wvous-br-corner = 14;

      # ────────── Dock persistent apps (in order) ──────────
      # Finder is always pinned to the left by macOS; no need to specify it here
      persistent-apps = [
        { app = "/Applications/cmux.app"; }
        { app = "/Applications/Raycast.app"; }
        { app = "/Applications/Arc.app"; }
        { app = "/Applications/Obsidian.app"; }
        { app = "/Applications/OrbStack.app"; }
        { app = "/Applications/Slack.app"; }
        { app = "/Applications/Discord.app"; }
        { app = "/Applications/LINE.app"; }
        { app = "/System/Applications/System Settings.app"; }
        { app = "/Applications/Nani.app"; }
      ];
    };

    # ────────── Screenshot ──────────
    screencapture.location = "~/Pictures";
    screencapture.target = "file";

    # ────────── Stage Manager ──────────
    WindowManager = {
      GloballyEnabled = false;
      AutoHide = true;
      HideDesktop = false;
      StageManagerHideWidgets = false;
      StandardHideWidgets = false;
    };

    # ────────── Trackpad gestures ──────────
    trackpad = {
      Clicking = true; # tap to click
      TrackpadRightClick = true; # two-finger right click
      TrackpadMomentumScroll = true;
      TrackpadPinch = true;
      TrackpadRotate = true;
      ActuateDetents = true;
      FirstClickThreshold = 0; # light click
      SecondClickThreshold = 0;
      ForceSuppressed = false; # Force Click enabled
      TrackpadFourFingerHorizSwipeGesture = 2;
      TrackpadFourFingerVertSwipeGesture = 2;
      TrackpadThreeFingerHorizSwipeGesture = 2;
      TrackpadThreeFingerVertSwipeGesture = 2;
      TrackpadTwoFingerFromRightEdgeSwipeGesture = 3;
    };

    # ────────── Lock screen ──────────
    screensaver.askForPassword = true;
    screensaver.askForPasswordDelay = 0; # require password immediately after sleep

    # ────────── Menu bar clock ──────────
    # Preserve current format: "Sun Mar 15 16:40:41"
    menuExtraClock = {
      Show24Hour = true;
      ShowSeconds = true;
      ShowDate = 1;
      ShowDayOfWeek = true;
    };

    # ────────── Custom preferences (not covered by native options) ──────────
    CustomUserPreferences = {
      "NSGlobalDomain" = {
        # Mouse cursor speed (fastest)
        "com.apple.mouse.scaling" = 3;
        # Save new documents locally instead of iCloud by default
        "NSDocumentSaveNewDocumentsToCloud" = false;
      };
      # Spotlight: disable all categories (using Raycast instead)
      "com.apple.Spotlight" = {
        "orderedItems" = [ ];
      };
      # Prevent .DS_Store file creation on network shares and USB drives
      "com.apple.desktopservices" = {
        "DSDontWriteNetworkStores" = true;
        "DSDontWriteUSBStores" = true;
      };
      # Hot corner modifier keys (0 = no modifier key required)
      "com.apple.dock" = {
        "wvous-tl-modifier" = 0;
        "wvous-tr-modifier" = 0;
        "wvous-bl-modifier" = 0;
        "wvous-br-modifier" = 0;
      };
      # Homerow: keyboard-driven macOS navigation
      "com.superultra.Homerow" = {
        "launch-at-login" = true;
        "scroll-shortcut" = "⌘J";
        "non-search-shortcut" = "⌘F";
        "scroll-px-per-ms" = 1.5;
        "theme-id" = "original";
        "auto-switch-input-source-id" = "com.google.inputmethod.Japanese.Roman";
        "use-search-predicate" = true;
        "dash-speed-multiplier" = 1;
        "map-arrow-keys-to-scroll" = false;
      };
    };
  };

  # ──────────────────────────────────────────────────────
  # Activation scripts (run on every darwin-rebuild switch)
  # ──────────────────────────────────────────────────────
  system.activationScripts.postActivation.text = ''
    # Stop Apple Music (rcd) from auto-launching
    launchctl unload -w /System/Library/LaunchAgents/com.apple.rcd.plist 2>/dev/null || true

    # Disable Spotlight keyboard shortcut (using Raycast instead)
    # Must run as the primary user, not root
    user="${config.system.primaryUser}"
    userHome="/Users/$user"
    /usr/libexec/PlistBuddy \
      -c "Set :AppleSymbolicHotKeys:64:enabled false" \
      "$userHome/Library/Preferences/com.apple.symbolichotkeys.plist" 2>/dev/null || \
    /usr/libexec/PlistBuddy \
      -c "Add :AppleSymbolicHotKeys:64:enabled bool false" \
      "$userHome/Library/Preferences/com.apple.symbolichotkeys.plist" 2>/dev/null || true

    # Disable automatic macOS updates (system-level, written to /Library/Preferences/)
    defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticallyInstallMacOSUpdates -bool false
    defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticDownload -bool false
    defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticCheckEnabled -bool false

    # Display sleep: never (both battery and charger)
    pmset -b displaysleep 0
    pmset -c displaysleep 0

    # NOTE: com.apple.universalaccess (reduceMotion, reduceTransparency) cannot be
    # written programmatically due to macOS TCC restrictions. Set manually in:
    # System Settings > Accessibility > Display
  '';

  homebrew = {
    enable = true;
    onActivation = {
      autoUpdate = true;
      upgrade = true;
      cleanup = "uninstall";
    };

    casks = [
      "appcleaner"
      "arc"
      "betterdisplay"
      "bitwarden"
      "chatgpt"
      "claude"
      "cmux"
      "deepl"
      "discord"
      "firefox"
      "font-jetbrains-mono"
      "ghostty"
      "google-chrome"
      "homerow"
      "karabiner-elements"
      "mactex"
      "nani"
      "obsidian"
      "orbstack"
      "raycast"
      "slack"
      "steam"
      "vimr"
      "visual-studio-code"
    ];

    taps = [
      "winebarrel/kasa"
    ];

    brews = [
      "winebarrel/kasa/kasa"
    ];

    masApps = {
      LINE = 539883307;
    };
  };
}
