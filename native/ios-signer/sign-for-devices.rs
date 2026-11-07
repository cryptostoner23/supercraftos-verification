//! Sign an app for a list of devices, addressed by UDID, without needing the
//! device to be connected over USB.
//!
//! This is the path used to sign the same bundle with several Apple accounts,
//! so that each account carries its own seven day provisioning profile and the
//! app can be rotated between them.
//!
//! Usage:
//!     sign-for-devices --apple-id <id> --udid <udid>[:<name>] --app <path.ipa> --out <signed.ipa>
//!
//! The password is read from the SUPERCRAFTOS_APPLE_PASSWORD environment
//! variable or, when it is not set, prompted for on the terminal without echo.
//! The two factor code is always prompted for, so it is never stored either.

use std::env;
use std::io::Write;
use std::path::PathBuf;

use isideload::{
    anisette::remote_v3::RemoteV3AnisetteProvider,
    auth::apple_account::{AppleAccount, TwoFactorCallbackParams, TwoFactorCallbackResponse},
    dev::{developer_session::DeveloperSession, devices::DevicesApi, teams::DeveloperTeam},
    sideload::{
        SideloaderBuilder, TeamSelection,
        builder::{ExtensionsBehavior, ExtensionsBehaviorSelection, MaxCertsBehavior},
    },
    util::{callbacks::ExtensionsBehaviorCallbackBox, fs_storage::FsStorage, keyring_storage::KeyringStorage},
};
use rustls::crypto::ring::default_provider;
use std::io::BufRead;
use tracing::Level;
use tracing_subscriber::FmtSubscriber;

struct Args {
    apple_id: String,
    app: PathBuf,
    out: PathBuf,
    devices: Vec<(String, String)>,
    machine_name: String,
    /// Where the Apple session is cached. A cached session means the
    /// password and the two factor code are only needed the first time.
    storage: Option<PathBuf>,
}

fn parse_args() -> Args {
    let mut apple_id = None;
    let mut app = None;
    let mut out = None;
    let mut devices: Vec<(String, String)> = Vec::new();
    let mut machine_name = "supercraftos-sign".to_string();
    let mut storage: Option<PathBuf> = None;
    let mut iterator = env::args().skip(1);
    while let Some(flag) = iterator.next() {
        let mut value = || iterator.next().unwrap_or_else(|| panic!("{flag} needs a value"));
        match flag.as_str() {
            "--apple-id" => apple_id = Some(value()),
            "--app" => app = Some(PathBuf::from(value())),
            "--out" => out = Some(PathBuf::from(value())),
            "--machine-name" => machine_name = value(),
            "--storage" => {
                storage = Some(PathBuf::from(value()));
            }
            "--udid" => {
                let raw = value();
                let (udid, name) = match raw.split_once(':') {
                    Some((udid, name)) => (udid.to_string(), name.to_string()),
                    None => (raw.clone(), "SuperCraftOS device".to_string()),
                };
                devices.push((udid, name));
            }
            other => panic!("unknown argument {other}"),
        }
    }
    Args {
        apple_id: apple_id.expect("--apple-id is required"),
        app: app.expect("--app is required"),
        out: out.expect("--out is required"),
        devices,
        machine_name,
        storage,
    }
}

fn read_password() -> String {
    if let Ok(value) = env::var("SUPERCRAFTOS_APPLE_PASSWORD") {
        if !value.is_empty() {
            return value;
        }
    }
    // Read the password without echoing it, so it never reaches the shell
    // history or the scrollback.
    print!("Apple ID password: ");
    let _ = std::io::stdout().flush();
    let mut password = String::new();
    let mut reader = std::io::BufReader::new(std::io::stdin());
    let _ = reader.read_line(&mut password);
    println!();
    password.trim_end_matches(['\r', '\n']).to_string()
}

#[tokio::main]
async fn main() {
    default_provider()
        .install_default()
        .expect("Failed to install the rustls crypto provider");
    isideload::init().expect("Failed to initialize error reporting");
    let subscriber = FmtSubscriber::builder().with_max_level(Level::INFO).finish();
    tracing::subscriber::set_global_default(subscriber).expect("Failed to set the subscriber");

    let args = parse_args();
    assert!(!args.devices.is_empty(), "at least one --udid is required");

    let get_2fa_code = async |_params: TwoFactorCallbackParams| {
        let mut code = String::new();
        println!("Enter the two factor code sent to your devices:");
        std::io::stdin().read_line(&mut code).unwrap();
        Ok(TwoFactorCallbackResponse::SubmitCode(code.trim().to_string()))
    };

    let password = read_password();

    // The default provider uses the desktop keyring. A headless VPS has no
    // D-Bus session or X display, so keep anisette alongside the signer's
    // existing filesystem session when --storage is supplied.
    let mut anisette = RemoteV3AnisetteProvider::default()
        .unwrap()
        .set_serial_number("2".to_string());
    if let Some(path) = &args.storage {
        anisette = anisette.set_storage(Box::new(FsStorage::new(path.join("anisette"))));
    }

    let mut account = AppleAccount::builder(&args.apple_id)
        .anisette_provider(anisette)
        .login(&password, get_2fa_code)
        .await
        .expect("Failed to sign in to the Apple account");

    let dev_session = DeveloperSession::from_account(&mut account)
        .await
        .expect("Failed to create a developer session");

    let team_selection_prompt = |teams: &Vec<DeveloperTeam>| {
        println!("Select a team:");
        for (index, team) in teams.iter().enumerate() {
            println!(
                "{}: {} ({})",
                index + 1,
                team.name.as_deref().unwrap_or("<Unnamed>"),
                team.team_id
            );
        }
        let mut input = String::new();
        std::io::stdin().read_line(&mut input).unwrap();
        let selection = input.trim().parse::<usize>().ok()?;
        if selection == 0 || selection > teams.len() {
            return None;
        }
        Some(teams[selection - 1].team_id.clone())
    };

    let cert_selection_prompt = async |certs: Vec<isideload::dev::certificates::DevelopmentCertificate>| {
        println!("The certificate limit was reached. Enter the numbers to revoke, comma separated:");
        for (index, cert) in certs.iter().enumerate() {
            println!("({}) {}", index + 1, cert.name.as_deref().unwrap_or("<Unnamed>"));
        }
        let mut input = String::new();
        std::io::stdin().read_line(&mut input).unwrap();
        let selections: Vec<usize> = input
            .trim()
            .split(',')
            .filter_map(|s| s.trim().parse::<usize>().ok())
            .filter(|&n| n > 0 && n <= certs.len())
            .collect();
        if selections.is_empty() {
            return Ok(None);
        }
        Ok(Some(
            selections
                .into_iter()
                .map(|n| certs[n - 1].serial_number.clone().unwrap_or_default())
                .collect::<Vec<_>>(),
        ))
    };

    // The session store. A file store keeps the session, so after the first
    // sign in the password and the two factor code are not needed again.
    let storage: Box<dyn isideload::util::storage::SideloadingStorage> = match &args.storage {
        Some(path) => Box::new(FsStorage::new(path.clone())),
        None => Box::new(KeyringStorage::new("supercraftos-sign".to_string())),
    };

    let mut sideloader = SideloaderBuilder::new(dev_session, args.apple_id.clone())
        .team_selection(TeamSelection::PromptOnce(team_selection_prompt))
        .max_certs_behavior(MaxCertsBehavior::Prompt(cert_selection_prompt))
        .extensions_behavior(ExtensionsBehaviorSelection::<ExtensionsBehaviorCallbackBox>::Fixed(
            ExtensionsBehavior::RegisterAll,
        ))
        .storage(storage)
        .machine_name(args.machine_name.clone())
        .build();

    let team = sideloader
        .get_team()
        .await
        .expect("Failed to read the developer team");

    for (udid, name) in &args.devices {
        sideloader
            .get_dev_session()
            .ensure_device_registered(&team, name, udid, None)
            .await
            .unwrap_or_else(|error| panic!("Failed to register the device {udid}: {error}"));
        println!("Registered {udid}");
    }

    let (signed, _special) = sideloader
        .sign_app(
            args.app.clone(),
            Some(team),
            false,
            None::<fn(f32) -> std::future::Ready<()>>,
            None,
            args.devices.first().map(|(udid, _)| udid.as_str()),
        )
        .await
        .unwrap_or_else(|error| panic!("Failed to sign the app: {error}"));

    std::fs::copy(&signed, &args.out).unwrap_or_else(|error| panic!("Failed to write {}: {error}", args.out.display()));
    println!("Signed bundle written to {}", args.out.display());
}
