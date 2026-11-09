<!-- Apple official documentation. Source of truth. -->
<!-- url: https://developer.apple.com/tutorials/data/documentation/xcode/distributing-your-app-for-beta-testing-and-releases.json -->
<!-- fetched: 2026-10-20T00:52:59+00:00 -->
<!-- sha256: e8d012776237f3171798fd9c6b8e54a3143c2d59732b0994c018154bcb8a901c -->
<!-- title: Distributing your app for beta testing and releases -->

# Distributing your app for beta testing and releases

Official page: <https://developer.apple.com/documentation/xcode/distributing-your-app-for-beta-testing-and-releases>

Overview
After you thoroughly test your app in Xcode, distribute it to beta testers or release it to users to run on their personal devices. Choose a distribution method based on your app’s platform and development stage, and whether you belong to the Apple Developer Program. Before you release your app to users, distribute your final build using one of the beta test methods.

If necessary, review doc://com.apple.Xcode/documentation/Xcode/preparing-your-app-for-distribution to complete the configuration of your project, before following these distribution steps.

[Session 10224: https://developer.apple.com/videos/play/wwdc2023/10224

]
Join the Apple Developer Program
Distribution methods range from exporting your app for test devices to uploading it to App Store Connect. You can use TestFlight to distribute beta builds to testers and collect feedback. If you want to distribute your app to registered devices, to beta testers using TestFlight, or through the App Store, join the Apple Developer Program. After you join the Apple Developer Program, Apple creates an App Store Connect account for you and you can start uploading builds.

Joining the Apple Developer Program provides access to the distribution methods, as well as capabilities you can add to your app. A capability grants your app access to an app service provided by Apple, such as CloudKit, Game Center, or In-App Purchase. To learn more about capabilities, see doc://com.apple.Xcode/documentation/Xcode/adding-capabilities-to-your-app.

Xcode uses cloud-managed signing certificates to automatically code sign your app. These signing certificates are associated with your Apple Developer Account, you can manage access to these certificates in App Store Connect. For information on managing access to certificate resources for your team, see https://developer.apple.com/help/app-store-connect/manage-your-team/add-and-edit-users.

To learn more about enrolling in the program, see https://developer.apple.com/programs/.

Combine multiplatform apps in a project or purchase
If you offer related apps on different platforms, combine them in one Xcode project or App Store purchase to make installation more convenient for users. To allow your customers to purchase related apps together from the App Store as a universal purchase or app bundle, see https://developer.apple.com/support/universal-purchase/.

Create an archive of your app
To use any of the distribution methods, first create an archive of your app. An archive is a build of your app, including debugging information, that Xcode stores in a bundle. Xcode repackages the archive’s contents based on the distribution configuration you choose for your distribution.

In the main window of your Xcode project, choose a scheme and a run destination to build for from the Scheme toolbar menu. Then, choose Product > Archive to build the targets included in that scheme, for the class of device you select, and create an archive that appears in the Archives organizer.

distributing-your-app-for-beta-testing-and-releases-1image

You can open the Archives organizer directly by choosing Window > Organizer. If you want to confirm your app is ready to submit to TestFlight or the App Store without submitting it yet, select your archive and then click Validate App. Xcode will perform a limited, automated initial validation of the app and provide feedback.

For a Mac app built with Mac Catalyst, create separate archives for the iPad and Mac version. When creating the archive for the Mac version, choose My Mac as the run destination.

[Earlier versions of Xcode didn’t allow you to build an archive with a simulator set as the run destination. In Xcode 15 and later, choosing to build an archive with a simulator as the run destination builds an archive with all the CPU architectures necessary to run on that class of device.

]
Select a method for distribution
You can export the archive or upload it to App Store Connect. If you export the archive, you can distribute it outside of the App Store. Otherwise, upload the archive to App Store Connect to distribute it through TestFlight or the App Store.

From the Organizer window in Xcode, select Archives in the sidebar and click Distribute App.

distributing-your-app-for-beta-testing-and-releases-2image

Select one of the following options to distribute using recommended settings:

Default settings to distribute through TestFlight and submit to the App Store. Use this option to update the build number of the content in your archive, perform automatic code signing, and upload your app with symbols.

TestFlight & App StoreDefault settings to distribute through TestFlight and restrict access to your team. Use this option to prevent a development build of your app from being submitted to the App Store.

TestFlight Internal OnlyDefault settings to distribute a version to test before release. Use this option to perform automatic code signing similar to the App Store distribution option and export to install on devices your team registers with App Store Connect. This distribution method isn’t available for apps built for Mac.

Release TestingDefault settings to distribute to members of your organization. Use this option if you’re a part of the https://developer.apple.com/programs/enterprise. This distribution method isn’t available for apps built for Mac.

EnterpriseDefault settings to distribute a macOS app directly. Use this option to notarize a Developer ID app for direct distribution. This distribution method is only available for apps built for Mac.

Direct DistributionDefault settings to distribute a version for debugging. Use this option to export a version to install and debug on devices your team registers with App Store Connect. This enables sandbox testing environments for some doc://com.apple.Xcode/documentation/Xcode/capabilities that support them.

DebuggingtermListAfter selecting a distribution option, click the Distribute button. Xcode begins processing, packaging, and uploading. Click the link at the end to access the builds page for the app on App Store Connect or click the Export button to access the assets locally.

[Before you upload your app to the App Store for the first time, create an app record to register your app with App Store Connect. If you haven’t done this already, Xcode asks you for the information it needs to create this record for you. For more information, see https://developer.apple.com/help/app-store-connect/create-an-app-record/add-a-new-app.

]
Create a custom distribution
To begin a custom distribution, which allows you to configure your own settings, click the Custom option.

distributing-your-app-for-beta-testing-and-releases-3image

Select from the following distribution methods:

Distribute using TestFlight or through the App Store.

App Store ConnectDistribute to a limited number of devices you register in App Store Connect. For more information on distributing to devices you register, see doc://com.apple.Xcode/documentation/Xcode/distributing-your-app-to-registered-devices.

Ad HocDistribute to members of your organization if you’re a part of the https://developer.apple.com/programs/enterprise and are ready to release your app to users in your organization.

EnterpriseDistribute a macOS app outside the App Store that is notarized by Apple or signed with a Developer ID. This distribution method is only available for apps built for Mac.

Developer IDDistribute to a limited number of devices you register in App Store Connect. For more information on distributing to devices you register, see doc://com.apple.Xcode/documentation/Xcode/distributing-your-app-to-registered-devices.

DevelopmentDistribute a macOS app without code signing. This distribution method is only available for apps built for Mac.

Copy ApptermListIf you choose App Store Connect or Developer ID as your distribution method, you select a destination option as well. You can choose to upload your build to the App Store, or Export your build locally to upload later.

distributing-your-app-for-beta-testing-and-releases-4image

When distributing your app on TestFlight or the App Store, choose how to manage symbols and build numbers:

distributing-your-app-for-beta-testing-and-releases-5image

Reduces the size of your app by stripping symbols from Swift standard libraries. This setting is only available if your project has embedded swift libraries.

Strip Swift symbolsAllows Apple to provide you with symbolicated crash logs and other diagnostic information. A symbolicated log replaces memory addresses in logs with human-readable function names and line numbers. The symbols can also be useful in compatibility testing of your app with Apple products and services.

Upload your app’s symbolsAllows Xcode to update the build number of all the content in your archive.

Manage version and build numberPrepares the app for distribution through TestFlight and restricts access to your team. Use this option to prevent a development build of your app from being submitted to the App Store.

TestFlight internal testing onlytermListWhen selecting a distribution method that involves code signing, select a method for code signing.

distributing-your-app-for-beta-testing-and-releases-6image

Choosing “Automatically manage signing” allows Xcode to manage signing for you. To manually sign your app, you use signing certificates. For information on sharing signing certificates, see doc://com.apple.Xcode/documentation/Xcode/sharing-your-teams-signing-certificates.

When packaging for self distribution using the Ad Hoc or Development option, choose whether to enable or disable App Thinning and configure on-demand resources settings. For more information about App Thinning and on-demand resources, see doc://com.apple.Xcode/documentation/Xcode/reducing-your-app-s-size and doc://com.apple.Xcode/documentation/Xcode/doing-advanced-optimization-to-further-reduce-your-app-s-size.

distributing-your-app-for-beta-testing-and-releases-7image

Distribute a beta version
To distribute a beta version of your app to offer a preview of an upcoming release, choose a distribution method that aligns with your testing resources:

Distribute a beta version of your app to internal and external testers using TestFlight. The TestFlight app allows invited users to install, beta test, provide feedback, and get updates of your app. Apple distributes the beta version for you, you manage the builds and users in App Store Connect. To learn more, see https://developer.apple.com/help/app-store-connect/test-a-beta-version/overview-of-testflight.

Distribute a beta version to registered devices in your developer account. Choose this option only if you can reserve a portion of your limited development devices for beta testing. To learn more, see doc://com.apple.Xcode/documentation/Xcode/distributing-your-app-to-registered-devices.

For macOS apps, distribute an Apple-notarized build to testers before you distribute the app through the App Store. To learn more, see doc://com.apple.documentation/documentation/Security/notarizing-macos-software-before-distribution.

distributing-your-app-for-beta-testing-and-releases-8image

Publish on the App Store
After beta testing your final build, submit it to App Review, then offer it on the App Store. For more information about the publishing process, see https://developer.apple.com/help/app-store-connect/manage-your-apps-availability/overview-of-publishing-your-app.

Go to https://developer.apple.com/app-store/review/ to review the App Store and Human Interface Guidelines. For platform specific guidance, see https://developer.apple.com/app-store/submitting.

You may need to enter additional information in App Store Connect before you can submit your app to App Review. After your app is uploaded or released, you can’t change some of this metadata, so it’s important to choose your settings carefully. For more information about this metadata, go to https://developer.apple.com/help/app-store-connect/reference/required-localizable-and-editable-properties in App Store Connect Help.

If you used TestFlight to distribute a beta version, and entered the additional information required by App Store for a release, just submit the last build that appears in App Store Connect to App Review.

distributing-your-app-for-beta-testing-and-releases-9image

If you didn’t distribute the final build using TestFlight, prepare your app for distribution and create an archive of your app. Validate the archive and fix any validation errors before continuing. Then, upload it to App Store Connect and wait for it to pass the App Store Connect validation tests.

To submit the build to App Review, go to https://developer.apple.com/help/app-store-connect/manage-submissions-to-app-review/submit-for-review.

Distribute outside of the App Store
For macOS apps, you can export a notarized app for distribution outside of the App Store, but you may first need to disable capabilities that require the Apple Developer Program membership first, then distribute the app yourself to users. Notarize all software that you distribute outside of the App Store. This includes system extensions and drivers. To learn more, see doc://com.apple.documentation/documentation/Security/notarizing-macos-software-before-distribution.

Distribute enterprise apps
There are also several options for distributing business, customized, or in-house apps as well. For details, see https://developer.apple.com/business/distribute/. If you join the https://developer.apple.com/programs/enterprise/, see https://help.apple.com/xcode/mac/current/#/devba5e7054d for enterprise-specific Xcode steps to export your app.

Review crash, diagnostic, and metrics reports
If you distribute your app using TestFlight or through the App Store, you can view crash and diagnostic reports that Apple generates for you in the organizer. You can also use the organizer to review feedback from beta testers. If you distribute your app through the App Store, you can view metrics reports in the organizer too. For more information, see doc://com.apple.Xcode/documentation/Xcode/acquiring-crash-reports-and-diagnostic-logs and doc://com.apple.Xcode/documentation/Xcode/viewing-and-responding-to-feedback. For more information about performance improvements, see doc://com.apple.Xcode/documentation/Xcode/improving-your-app-s-performance and doc://com.apple.Xcode/documentation/Xcode/analyzing-the-performance-of-your-shipping-app.

content
