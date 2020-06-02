// Installer script for qt.
// Based on https://github.com/rabits/dockerfiles/blob/master/5.13-desktop/extract-qt-installer.sh
// See https://doc.qt.io/qtinstallerframework/noninteractive.html

function Controller() {
    //installer.autoRejectMessageBoxes();
    installer.installationFinished.connect(function() {
        gui.clickButton(buttons.NextButton);
    })
}

Controller.prototype.WelcomePageCallback = function() {
    console.log("Welcome Page");
    gui.clickButton(buttons.NextButton, 3000);
}

Controller.prototype.CredentialsPageCallback = function() {
    gui.clickButton(buttons.CommitButton);
}

Controller.prototype.IntroductionPageCallback = function() {
    gui.clickButton(buttons.NextButton);
}

Controller.prototype.TargetDirectoryPageCallback = function()
{
    var short_version = installer.environmentVariable("QT_SHORT_VERSION");
    var path = "/opt/qt-" + short_version

    gui.currentPageWidget().TargetDirectoryLineEdit.setText(path);
    gui.clickButton(buttons.NextButton);
}

Controller.prototype.ComponentSelectionPageCallback = function() {
    var major_version = installer.environmentVariable("QT_MAJOR_VERSION");
    var minor_version = installer.environmentVariable("QT_MINOR_VERSION");
    var patch_version = installer.environmentVariable("QT_PATCH_VERSION");
    var qt_version = "qt.qt" + major_version + "." + major_version + minor_version + patch_version;

    var components = [
      qt_version+ ".gcc_64",
      qt_version+ ".qtwebengine",
      qt_version+ ".qtnetworkauth",
    ]
    console.log("Select components");
    var widget = gui.currentPageWidget();
    for (var i=0; i < components.length; i++){
        widget.selectComponent(components[i]);
        console.log("selected: " + components[i])
    }
    gui.clickButton(buttons.NextButton);
}

Controller.prototype.LicenseAgreementPageCallback = function() {
    console.log("Accept license agreement");
    var widget = gui.currentPageWidget();
    if (widget != null) {
        widget.AcceptLicenseRadioButton.setChecked(true);
    }
    gui.clickButton(buttons.NextButton);
}

Controller.prototype.ReadyForInstallationPageCallback = function() {
    console.log("Ready to install");
    gui.clickButton(buttons.CommitButton);
}

Controller.prototype.FinishedPageCallback = function() {
    var widget = gui.currentPageWidget();
    if (widget.LaunchQtCreatorCheckBoxForm) {
        widget.LaunchQtCreatorCheckBoxForm.launchQtCreatorCheckBox.setChecked(false);
    }
    gui.clickButton(buttons.FinishButton);
}
