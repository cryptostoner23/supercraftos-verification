<!-- Apple official documentation. Source of truth. -->
<!-- url: https://developer.apple.com/tutorials/data/documentation/bundleresources/entitlements.json -->
<!-- fetched: 2026-10-20T00:53:00+00:00 -->
<!-- sha256: 2fa664f646c5018ac7b60527890a7999b2536d95507379fa17b1e7cae085f14e -->
<!-- title: Entitlements -->

# Entitlements

Official page: <https://developer.apple.com/documentation/bundleresources/entitlements>

EntitlementssymboldictionarydetailsDetailsDiscussion
An entitlement is a right or privilege that grants particular capabilities to an executable. For example, an app needs the doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.homekit — along with explicit user consent — to access a user’s home automation network. An app stores its entitlements as key-value pairs embedded in the code signature of its binary executable.

You configure entitlements for your app by declaring capabilities for a target in Xcode; see doc://com.apple.documentation/documentation/Xcode/capabilities. Xcode records capabilities that you add in a property list file with the .entitlements extension. When code signing your app, Xcode combines the entitlements file, information from your developer account, and other project information to apply a final set of entitlements to your app.

You typically let Xcode manage the entitlements file for you. For information on manually editing the file, see doc://com.apple.documentation/documentation/Xcode/editing-property-list-files.

content
## Essentials
- doc://com.apple.documentation/documentation/Xcode/adding-capabilities-to-your-app
- doc://com.apple.bundleresources/documentation/BundleResources/diagnosing-issues-with-entitlements
- doc://com.apple.documentation/documentation/Xcode/signing-a-daemon-with-a-restricted-entitlement

## Accessibility
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.accessibility.merchant-api-control

## Accessory Access
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.accessory-access.usb

## AccessorySetupKit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.accessory-setup-discovery-extension

## Accessory Transport Extension
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.accessory-transport-extension
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.accessory-transport-security
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.accessory-data-provider

## Alternative browser engines
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.embedded-web-browser-engine
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.embedded-web-browser-engine.engine-association
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.web-browser-engine.host
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.web-browser-engine.networking
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.web-browser-engine.webcontent
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.web-browser-engine.rendering
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.memory.transfer_accept
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.memory.transfer_send
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.web-browser-engine.restrict.notifyd

## Alternative app marketplaces
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.marketplace.app-installation

## App Clips
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.parent-application-identifiers
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.associated-appclip-app-identifiers
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.on-demand-install-capable

## AppIntents
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.side-button-access.allow

## AppMigrationKit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.app-migration.data-container-access

## Authentication
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.authentication-services.account-creation-requires-phone-number
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.authentication-services.autofill-credential-provider
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.applesignin

## Background tasks
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.background-tasks.continued-processing.gpu
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.background-tasks.continued-processing.inference

## CallKit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.calling-app

## CarPlay
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.carplay-audio
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.carplay-charging
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.carplay-communication
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.carplay-driving-task
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.carplay-fueling
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.carplay-maps
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.carplay-parking
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.carplay-public-safety
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.carplay-quick-ordering
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.carplay-video
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.carplay-voice-based-conversation
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.carplay-messaging
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.playable-content

## CloudKit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.icloud-extended-share-access

## Contacts
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.contacts.notes

## CoreTelephony
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.CommCenter.fine-grained

## Declared Age Range
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.declared-age-range

## Device Management
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.automated-device-enrollment.add-devices
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.enrollment-sso-capable

## Education
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.ClassKit-environment
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.automatic-assessment-configuration

## Email clients
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.mail-client

## EnergyKit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.energykit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.energykit.loadevents-experience

## Enterprise
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.app-compute-category
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.screen-capture.include-passthrough
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.arkit.main-camera-access.allow
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.arkit.object-tracking-parameter-adjustment.allow
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.arkit.barcode-detection.allow
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.arkit.camera-region.allow
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.arkit.shared-coordinate-space.allow
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.protected-content
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.window-body-follow
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.coreml.neural-engine-access
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.avfoundation.uvc-device-access
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.arkit.visual-fidelity.allow

## Exposure notification
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.exposure-notification

## Family controls
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.family-controls
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.family-controls.app-and-website-usage

## File provider
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.fileprovider.testing-mode

## FinanceKit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.financekit

## Foundation Models
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.private-cloud-compute

## FSKit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.fskit.fsmodule

## Games
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.game-center

## Group activities
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.group-session

## Health
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.healthkit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.healthkit.access
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.healthkit.background-delivery
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.health.fall-detection
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.healthkit.recalibrate-estimates
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.healthkit.research

## Home automation
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.homekit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.matter.allow-setup-payload

## Hypervisor
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.security.hypervisor
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.vm.hypervisor
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.vm.device-access
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.vm.networking
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.security.virtualization

## iCloud
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.icloud-container-development-container-identifiers
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.icloud-container-environment
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.icloud-container-identifiers
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.icloud-services
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.ubiquity-kvstore-identifier

## IdentityDocumentServices
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.identity-document-services.document-provider.mobile-document-types

## Journaling Suggestions
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.journal.allow

## LiveCommunicationKit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.calling-app
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.dialing-app
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.conversation-accessibility

## Location
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.location.push

## Managed App Distribution
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.managed-app-distribution.install-ui

## Media
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.media-device-extension
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.coremotion.head-pose
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.spatial-audio.profile-access
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.avfoundation.multitasking-camera-access
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.media-device-discovery-extension

## Memory
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.kernel.increased-memory-limit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.kernel.extended-virtual-addressing

## Metal
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.sustained-execution

## Messages
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.messages.critical-messaging
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.messaging-app

## MessageUI
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.upi-device-validation

## Navigation
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.navigation-app

## Networking
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.networking.networkextension
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.networking.vpn.api
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.associated-domains
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.networking.multicast
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.associated-domains.applinks.read-write
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.networking.manage-thread-network-credentials
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.networking.slicing.appcategory
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.networking.slicing.trafficcategory
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.networking.vmnet
- doc://com.apple.bundleresources/documentation/BundleResources/Configuring-your-app-for-ultra-constrained-networks
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.networking.carrier-constrained.appcategory
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.networking.carrier-constrained.app-optimized

## Notifications
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/aps-environment
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.aps-environment
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.usernotifications.critical-alerts
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.usernotifications.filtering

## PassKit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.passkit.pass-presentation-suppression

## Privacy
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.device-information.user-assigned-device-name

## Push to Talk
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.push-to-talk

## SafetyKit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.severe-vehicular-crash-event

## SecureElementCredential
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.secure-element-credential
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.secure-element-credential.default-contactless-app

## Security
- doc://com.apple.bundleresources/documentation/BundleResources/security-entitlements
- doc://com.apple.documentation/documentation/Security/app-sandbox
- doc://com.apple.documentation/documentation/Security/hardened-runtime
- doc://com.apple.documentation/documentation/Xcode/enabling-enhanced-security-for-your-app

## Sensitive Content Analysis
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.sensitivecontentanalysis.client

## Sensors
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.sensorkit.reader.allow

## Siri
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.siri

## Suggested Actions
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.suggested-actions

## StoreKit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.storekit.custom-purchase-link.allowed-regions
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.storekit.external-link.account
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.storekit.external-purchase
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.storekit.external-purchase-link
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.storekit.external-purchase-link-streaming

## System
- doc://com.apple.bundleresources/documentation/BundleResources/driverkit
- doc://com.apple.bundleresources/documentation/BundleResources/system-extensions

## TelephonyMessagingKit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.carrier-messaging-app

## Translation
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.translation-app

## TrustInsights
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.trustinsights.base

## TV
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.user-management
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.video-subscriber-single-sign-on
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.smoot.subscriptionservice

## visionOS
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.low-latency-streaming
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.foveated-streaming-session
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.foveated-streaming-provider

## Wallet
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.pass-type-identifiers
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.in-app-payments
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.in-app-identity-presentment
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.in-app-identity-presentment.merchant-identifiers
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.proximity-reader.identity.display
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.proximity-reader.identity.read

## WeatherKit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.weatherkit

## Web browsers
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.web-browser
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.web-browser.public-key-credential
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.browser.app-installation

## Wireless interfaces
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.networking.wifi-info
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.external-accessory.wireless-configuration
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.networking.multipath
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.networking.HotspotConfiguration
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.networking.HotspotHelper
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.nfc.readersession.felica.systemcodes
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.nfc.readersession.formats
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.nfc.readersession.iso7816.select-identifiers
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.nfc.hce
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.nfc.hce.iso7816.select-identifier-prefixes
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.nfc.hce.default-contactless-app

## Wireless insights
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.wireless-insights.service-predictions

## Deprecated entitlements
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.maps
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/inter-app-audio
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.security.files.all

## ScreenCaptureKit
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.persistent-content-capture

## Wi-Fi Aware
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.wifi-aware

## Wi-Fi Infrastructure
- doc://com.apple.bundleresources/documentation/BundleResources/Entitlements/com.apple.developer.wifi-infrastructure
