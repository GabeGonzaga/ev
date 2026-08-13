#![allow(clippy::redundant_closure_call)]
#![allow(clippy::needless_lifetimes)]
#![allow(clippy::match_single_binding)]
#![allow(clippy::clone_on_copy)]

#[doc = r" Error types."]
pub mod error {
    #[doc = r" Error from a `TryFrom` or `FromStr` implementation."]
    pub struct ConversionError(::std::borrow::Cow<'static, str>);
    impl ::std::error::Error for ConversionError {}
    impl ::std::fmt::Display for ConversionError {
        fn fmt(&self, f: &mut ::std::fmt::Formatter<'_>) -> Result<(), ::std::fmt::Error> {
            ::std::fmt::Display::fmt(&self.0, f)
        }
    }
    impl ::std::fmt::Debug for ConversionError {
        fn fmt(&self, f: &mut ::std::fmt::Formatter<'_>) -> Result<(), ::std::fmt::Error> {
            ::std::fmt::Debug::fmt(&self.0, f)
        }
    }
    impl From<&'static str> for ConversionError {
        fn from(value: &'static str) -> Self {
            Self(value.into())
        }
    }
    impl From<String> for ConversionError {
        fn from(value: String) -> Self {
            Self(value.into())
        }
    }
}
#[doc = "base64 of a mono 16-bit PCM WAV."]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"Audio\","]
#[doc = "  \"description\": \"base64 of a mono 16-bit PCM WAV.\","]
#[doc = "  \"type\": \"string\","]
#[doc = "  \"maxLength\": 8000000"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Serialize, Clone, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
#[serde(transparent)]
pub struct Audio(::std::string::String);
impl ::std::ops::Deref for Audio {
    type Target = ::std::string::String;
    fn deref(&self) -> &::std::string::String {
        &self.0
    }
}
impl ::std::convert::From<Audio> for ::std::string::String {
    fn from(value: Audio) -> Self {
        value.0
    }
}
impl ::std::str::FromStr for Audio {
    type Err = self::error::ConversionError;
    fn from_str(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        if value.chars().count() > 8000000usize {
            return Err("longer than 8000000 characters".into());
        }
        Ok(Self(value.to_string()))
    }
}
impl ::std::convert::TryFrom<&str> for Audio {
    type Error = self::error::ConversionError;
    fn try_from(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<&::std::string::String> for Audio {
    type Error = self::error::ConversionError;
    fn try_from(
        value: &::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<::std::string::String> for Audio {
    type Error = self::error::ConversionError;
    fn try_from(
        value: ::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl<'de> ::serde::Deserialize<'de> for Audio {
    fn deserialize<D>(deserializer: D) -> ::std::result::Result<Self, D::Error>
    where
        D: ::serde::Deserializer<'de>,
    {
        ::std::string::String::deserialize(deserializer)?
            .parse()
            .map_err(|e: self::error::ConversionError| {
                <D::Error as ::serde::de::Error>::custom(e.to_string())
            })
    }
}
#[doc = "Recorded speech, on its way to be transcribed.\n\nThe host captures, because the microphone is a TCC surface and TCC grants\nattach to a code signature. The core transcribes, because that is where\n`SpeechRecognizer` lives and where the engine stays replaceable (ADR 0018).\n\nBase64 rather than a file path: a path means the audio is written to disk\nby one process and read by another, and neither owns deleting it. ~2.5\nseconds of 16 kHz mono is about 100 KB encoded, which is nothing on a local\nsocket."]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"AudioSubmit\","]
#[doc = "  \"description\": \"Recorded speech, on its way to be transcribed.\\n\\nThe host captures, because the microphone is a TCC surface and TCC grants\\nattach to a code signature. The core transcribes, because that is where\\n`SpeechRecognizer` lives and where the engine stays replaceable (ADR 0018).\\n\\nBase64 rather than a file path: a path means the audio is written to disk\\nby one process and read by another, and neither owns deleting it. ~2.5\\nseconds of 16 kHz mono is about 100 KB encoded, which is nothing on a local\\nsocket.\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"required\": ["]
#[doc = "    \"audio\""]
#[doc = "  ],"]
#[doc = "  \"properties\": {"]
#[doc = "    \"audio\": {"]
#[doc = "      \"title\": \"Audio\","]
#[doc = "      \"description\": \"base64 of a mono 16-bit PCM WAV.\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"maxLength\": 8000000"]
#[doc = "    },"]
#[doc = "    \"locale\": {"]
#[doc = "      \"title\": \"Locale\","]
#[doc = "      \"description\": \"The language to transcribe as. Never 'auto': auto-detect is unreliable on short utterances, and a misdetected language becomes a tool argument.\","]
#[doc = "      \"default\": null,"]
#[doc = "      \"anyOf\": ["]
#[doc = "        {"]
#[doc = "          \"type\": \"string\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"type\": \"null\""]
#[doc = "        }"]
#[doc = "      ]"]
#[doc = "    },"]
#[doc = "    \"sample_rate\": {"]
#[doc = "      \"title\": \"Sample Rate\","]
#[doc = "      \"default\": 16000,"]
#[doc = "      \"type\": \"integer\","]
#[doc = "      \"maximum\": 48000.0,"]
#[doc = "      \"minimum\": 8000.0"]
#[doc = "    },"]
#[doc = "    \"type\": {"]
#[doc = "      \"title\": \"Type\","]
#[doc = "      \"default\": \"audio.submit\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"const\": \"audio.submit\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct AudioSubmit {
    #[doc = "base64 of a mono 16-bit PCM WAV."]
    pub audio: Audio,
    #[doc = "The language to transcribe as. Never 'auto': auto-detect is unreliable on short utterances, and a misdetected language becomes a tool argument."]
    #[serde(default, skip_serializing_if = "::std::option::Option::is_none")]
    pub locale: ::std::option::Option<::std::string::String>,
    #[serde(default = "defaults::default_u64::<i64, 16000>")]
    pub sample_rate: i64,
    #[serde(rename = "type", default = "defaults::audio_submit_type")]
    pub type_: ::std::string::String,
}
impl AudioSubmit {
    pub fn builder() -> builder::AudioSubmit {
        Default::default()
    }
}
#[doc = "`Command`"]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"Command\","]
#[doc = "  \"oneOf\": ["]
#[doc = "    {"]
#[doc = "      \"$ref\": \"#/$defs/Hello\""]
#[doc = "    },"]
#[doc = "    {"]
#[doc = "      \"$ref\": \"#/$defs/UtteranceSubmit\""]
#[doc = "    },"]
#[doc = "    {"]
#[doc = "      \"$ref\": \"#/$defs/AudioSubmit\""]
#[doc = "    },"]
#[doc = "    {"]
#[doc = "      \"$ref\": \"#/$defs/VisionSubmit\""]
#[doc = "    },"]
#[doc = "    {"]
#[doc = "      \"$ref\": \"#/$defs/ConfirmationRespond\""]
#[doc = "    },"]
#[doc = "    {"]
#[doc = "      \"$ref\": \"#/$defs/HistoryQuery\""]
#[doc = "    },"]
#[doc = "    {"]
#[doc = "      \"$ref\": \"#/$defs/PermissionReport\""]
#[doc = "    },"]
#[doc = "    {"]
#[doc = "      \"$ref\": \"#/$defs/SessionCancel\""]
#[doc = "    }"]
#[doc = "  ],"]
#[doc = "  \"discriminator\": {"]
#[doc = "    \"mapping\": {"]
#[doc = "      \"audio.submit\": \"#/$defs/AudioSubmit\","]
#[doc = "      \"confirmation.respond\": \"#/$defs/ConfirmationRespond\","]
#[doc = "      \"hello\": \"#/$defs/Hello\","]
#[doc = "      \"history.query\": \"#/$defs/HistoryQuery\","]
#[doc = "      \"permission.report\": \"#/$defs/PermissionReport\","]
#[doc = "      \"session.cancel\": \"#/$defs/SessionCancel\","]
#[doc = "      \"utterance.submit\": \"#/$defs/UtteranceSubmit\","]
#[doc = "      \"vision.submit\": \"#/$defs/VisionSubmit\""]
#[doc = "    },"]
#[doc = "    \"propertyName\": \"type\""]
#[doc = "  }"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(untagged)]
pub enum Command {
    Hello(Hello),
    UtteranceSubmit(UtteranceSubmit),
    AudioSubmit(AudioSubmit),
    VisionSubmit(VisionSubmit),
    ConfirmationRespond(ConfirmationRespond),
    HistoryQuery(HistoryQuery),
    PermissionReport(PermissionReport),
    SessionCancel(SessionCancel),
}
impl ::std::convert::From<Hello> for Command {
    fn from(value: Hello) -> Self {
        Self::Hello(value)
    }
}
impl ::std::convert::From<UtteranceSubmit> for Command {
    fn from(value: UtteranceSubmit) -> Self {
        Self::UtteranceSubmit(value)
    }
}
impl ::std::convert::From<AudioSubmit> for Command {
    fn from(value: AudioSubmit) -> Self {
        Self::AudioSubmit(value)
    }
}
impl ::std::convert::From<VisionSubmit> for Command {
    fn from(value: VisionSubmit) -> Self {
        Self::VisionSubmit(value)
    }
}
impl ::std::convert::From<ConfirmationRespond> for Command {
    fn from(value: ConfirmationRespond) -> Self {
        Self::ConfirmationRespond(value)
    }
}
impl ::std::convert::From<HistoryQuery> for Command {
    fn from(value: HistoryQuery) -> Self {
        Self::HistoryQuery(value)
    }
}
impl ::std::convert::From<PermissionReport> for Command {
    fn from(value: PermissionReport) -> Self {
        Self::PermissionReport(value)
    }
}
impl ::std::convert::From<SessionCancel> for Command {
    fn from(value: SessionCancel) -> Self {
        Self::SessionCancel(value)
    }
}
#[doc = "`ConfirmationRequired`"]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"ConfirmationRequired\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"required\": ["]
#[doc = "    \"id\","]
#[doc = "    \"risk\","]
#[doc = "    \"tool\""]
#[doc = "  ],"]
#[doc = "  \"properties\": {"]
#[doc = "    \"arguments\": {"]
#[doc = "      \"title\": \"Arguments\","]
#[doc = "      \"type\": \"object\","]
#[doc = "      \"additionalProperties\": true"]
#[doc = "    },"]
#[doc = "    \"id\": {"]
#[doc = "      \"title\": \"Id\","]
#[doc = "      \"description\": \"Echoed back in confirmation.respond.\","]
#[doc = "      \"type\": \"string\""]
#[doc = "    },"]
#[doc = "    \"risk\": {"]
#[doc = "      \"$ref\": \"#/$defs/RiskLevel\""]
#[doc = "    },"]
#[doc = "    \"tool\": {"]
#[doc = "      \"title\": \"Tool\","]
#[doc = "      \"type\": \"string\""]
#[doc = "    },"]
#[doc = "    \"type\": {"]
#[doc = "      \"title\": \"Type\","]
#[doc = "      \"default\": \"confirmation.required\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"const\": \"confirmation.required\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct ConfirmationRequired {
    #[serde(default, skip_serializing_if = "::serde_json::Map::is_empty")]
    pub arguments: ::serde_json::Map<::std::string::String, ::serde_json::Value>,
    #[doc = "Echoed back in confirmation.respond."]
    pub id: ::std::string::String,
    pub risk: RiskLevel,
    pub tool: ::std::string::String,
    #[serde(rename = "type", default = "defaults::confirmation_required_type")]
    pub type_: ::std::string::String,
}
impl ConfirmationRequired {
    pub fn builder() -> builder::ConfirmationRequired {
        Default::default()
    }
}
#[doc = "`ConfirmationRespond`"]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"ConfirmationRespond\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"required\": ["]
#[doc = "    \"granted\","]
#[doc = "    \"request\""]
#[doc = "  ],"]
#[doc = "  \"properties\": {"]
#[doc = "    \"granted\": {"]
#[doc = "      \"title\": \"Granted\","]
#[doc = "      \"type\": \"boolean\""]
#[doc = "    },"]
#[doc = "    \"request\": {"]
#[doc = "      \"title\": \"Request\","]
#[doc = "      \"description\": \"The id of the confirmation.required event.\","]
#[doc = "      \"type\": \"string\""]
#[doc = "    },"]
#[doc = "    \"type\": {"]
#[doc = "      \"title\": \"Type\","]
#[doc = "      \"default\": \"confirmation.respond\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"const\": \"confirmation.respond\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct ConfirmationRespond {
    pub granted: bool,
    #[doc = "The id of the confirmation.required event."]
    pub request: ::std::string::String,
    #[serde(rename = "type", default = "defaults::confirmation_respond_type")]
    pub type_: ::std::string::String,
}
impl ConfirmationRespond {
    pub fn builder() -> builder::ConfirmationRespond {
        Default::default()
    }
}
#[doc = "Everything that crosses the socket, for the generated schema's benefit.\n\nEach line on the wire is one of these, so a generator emits one type per\nlanguage rather than three unrelated roots."]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"$id\": \"https://ev.local/protocol/ev.schema.json\","]
#[doc = "  \"title\": \"Envelope\","]
#[doc = "  \"description\": \"Everything that crosses the socket, for the generated schema's benefit.\\n\\nEach line on the wire is one of these, so a generator emits one type per\\nlanguage rather than three unrelated roots.\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"properties\": {"]
#[doc = "    \"event\": {"]
#[doc = "      \"title\": \"Event\","]
#[doc = "      \"default\": null,"]
#[doc = "      \"anyOf\": ["]
#[doc = "        {"]
#[doc = "          \"oneOf\": ["]
#[doc = "            {"]
#[doc = "              \"$ref\": \"#/$defs/TranscriptionPartial\""]
#[doc = "            },"]
#[doc = "            {"]
#[doc = "              \"$ref\": \"#/$defs/SpeechRequested\""]
#[doc = "            },"]
#[doc = "            {"]
#[doc = "              \"$ref\": \"#/$defs/ConfirmationRequired\""]
#[doc = "            },"]
#[doc = "            {"]
#[doc = "              \"$ref\": \"#/$defs/ToolCompleted\""]
#[doc = "            },"]
#[doc = "            {"]
#[doc = "              \"$ref\": \"#/$defs/StateChanged\""]
#[doc = "            },"]
#[doc = "            {"]
#[doc = "              \"$ref\": \"#/$defs/PermissionChanged\""]
#[doc = "            }"]
#[doc = "          ],"]
#[doc = "          \"discriminator\": {"]
#[doc = "            \"mapping\": {"]
#[doc = "              \"confirmation.required\": \"#/$defs/ConfirmationRequired\","]
#[doc = "              \"permission.changed\": \"#/$defs/PermissionChanged\","]
#[doc = "              \"speech.requested\": \"#/$defs/SpeechRequested\","]
#[doc = "              \"state.changed\": \"#/$defs/StateChanged\","]
#[doc = "              \"tool.completed\": \"#/$defs/ToolCompleted\","]
#[doc = "              \"transcription.partial\": \"#/$defs/TranscriptionPartial\""]
#[doc = "            },"]
#[doc = "            \"propertyName\": \"type\""]
#[doc = "          }"]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"type\": \"null\""]
#[doc = "        }"]
#[doc = "      ]"]
#[doc = "    },"]
#[doc = "    \"page\": {"]
#[doc = "      \"default\": null,"]
#[doc = "      \"anyOf\": ["]
#[doc = "        {"]
#[doc = "          \"$ref\": \"#/$defs/HistoryPage\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"type\": \"null\""]
#[doc = "        }"]
#[doc = "      ]"]
#[doc = "    },"]
#[doc = "    \"request\": {"]
#[doc = "      \"default\": null,"]
#[doc = "      \"anyOf\": ["]
#[doc = "        {"]
#[doc = "          \"$ref\": \"#/$defs/Request\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"type\": \"null\""]
#[doc = "        }"]
#[doc = "      ]"]
#[doc = "    },"]
#[doc = "    \"response\": {"]
#[doc = "      \"default\": null,"]
#[doc = "      \"anyOf\": ["]
#[doc = "        {"]
#[doc = "          \"$ref\": \"#/$defs/Response\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"type\": \"null\""]
#[doc = "        }"]
#[doc = "      ]"]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false,"]
#[doc = "  \"x-ev-protocol-version\": \"1.5\""]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct Envelope {
    #[serde(default, skip_serializing_if = "::std::option::Option::is_none")]
    pub event: ::std::option::Option<EnvelopeEvent>,
    #[serde(default, skip_serializing_if = "::std::option::Option::is_none")]
    pub page: ::std::option::Option<HistoryPage>,
    #[serde(default, skip_serializing_if = "::std::option::Option::is_none")]
    pub request: ::std::option::Option<Request>,
    #[serde(default, skip_serializing_if = "::std::option::Option::is_none")]
    pub response: ::std::option::Option<Response>,
}
impl ::std::default::Default for Envelope {
    fn default() -> Self {
        Self {
            event: Default::default(),
            page: Default::default(),
            request: Default::default(),
            response: Default::default(),
        }
    }
}
impl Envelope {
    pub fn builder() -> builder::Envelope {
        Default::default()
    }
}
#[doc = "`EnvelopeEvent`"]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"oneOf\": ["]
#[doc = "    {"]
#[doc = "      \"$ref\": \"#/$defs/TranscriptionPartial\""]
#[doc = "    },"]
#[doc = "    {"]
#[doc = "      \"$ref\": \"#/$defs/SpeechRequested\""]
#[doc = "    },"]
#[doc = "    {"]
#[doc = "      \"$ref\": \"#/$defs/ConfirmationRequired\""]
#[doc = "    },"]
#[doc = "    {"]
#[doc = "      \"$ref\": \"#/$defs/ToolCompleted\""]
#[doc = "    },"]
#[doc = "    {"]
#[doc = "      \"$ref\": \"#/$defs/StateChanged\""]
#[doc = "    },"]
#[doc = "    {"]
#[doc = "      \"$ref\": \"#/$defs/PermissionChanged\""]
#[doc = "    }"]
#[doc = "  ],"]
#[doc = "  \"discriminator\": {"]
#[doc = "    \"mapping\": {"]
#[doc = "      \"confirmation.required\": \"#/$defs/ConfirmationRequired\","]
#[doc = "      \"permission.changed\": \"#/$defs/PermissionChanged\","]
#[doc = "      \"speech.requested\": \"#/$defs/SpeechRequested\","]
#[doc = "      \"state.changed\": \"#/$defs/StateChanged\","]
#[doc = "      \"tool.completed\": \"#/$defs/ToolCompleted\","]
#[doc = "      \"transcription.partial\": \"#/$defs/TranscriptionPartial\""]
#[doc = "    },"]
#[doc = "    \"propertyName\": \"type\""]
#[doc = "  }"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(untagged)]
pub enum EnvelopeEvent {
    TranscriptionPartial(TranscriptionPartial),
    SpeechRequested(SpeechRequested),
    ConfirmationRequired(ConfirmationRequired),
    ToolCompleted(ToolCompleted),
    StateChanged(StateChanged),
    PermissionChanged(PermissionChanged),
}
impl ::std::convert::From<TranscriptionPartial> for EnvelopeEvent {
    fn from(value: TranscriptionPartial) -> Self {
        Self::TranscriptionPartial(value)
    }
}
impl ::std::convert::From<SpeechRequested> for EnvelopeEvent {
    fn from(value: SpeechRequested) -> Self {
        Self::SpeechRequested(value)
    }
}
impl ::std::convert::From<ConfirmationRequired> for EnvelopeEvent {
    fn from(value: ConfirmationRequired) -> Self {
        Self::ConfirmationRequired(value)
    }
}
impl ::std::convert::From<ToolCompleted> for EnvelopeEvent {
    fn from(value: ToolCompleted) -> Self {
        Self::ToolCompleted(value)
    }
}
impl ::std::convert::From<StateChanged> for EnvelopeEvent {
    fn from(value: StateChanged) -> Self {
        Self::StateChanged(value)
    }
}
impl ::std::convert::From<PermissionChanged> for EnvelopeEvent {
    fn from(value: PermissionChanged) -> Self {
        Self::PermissionChanged(value)
    }
}
#[doc = "First message on every connection. Nothing else is served until it is\naccepted."]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"Hello\","]
#[doc = "  \"description\": \"First message on every connection. Nothing else is served until it is\\naccepted.\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"required\": ["]
#[doc = "    \"client\","]
#[doc = "    \"protocol\""]
#[doc = "  ],"]
#[doc = "  \"properties\": {"]
#[doc = "    \"client\": {"]
#[doc = "      \"title\": \"Client\","]
#[doc = "      \"description\": \"Who is connecting, for the log.\","]
#[doc = "      \"type\": \"string\""]
#[doc = "    },"]
#[doc = "    \"protocol\": {"]
#[doc = "      \"title\": \"Protocol\","]
#[doc = "      \"description\": \"The protocol version the client speaks.\","]
#[doc = "      \"type\": \"string\""]
#[doc = "    },"]
#[doc = "    \"type\": {"]
#[doc = "      \"title\": \"Type\","]
#[doc = "      \"default\": \"hello\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"const\": \"hello\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct Hello {
    #[doc = "Who is connecting, for the log."]
    pub client: ::std::string::String,
    #[doc = "The protocol version the client speaks."]
    pub protocol: ::std::string::String,
    #[serde(rename = "type", default = "defaults::hello_type")]
    pub type_: ::std::string::String,
}
impl Hello {
    pub fn builder() -> builder::Hello {
        Default::default()
    }
}
#[doc = "What a `history.query` answers with, inside the response payload."]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"HistoryPage\","]
#[doc = "  \"description\": \"What a `history.query` answers with, inside the response payload.\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"properties\": {"]
#[doc = "    \"entries\": {"]
#[doc = "      \"title\": \"Entries\","]
#[doc = "      \"type\": \"array\","]
#[doc = "      \"items\": {"]
#[doc = "        \"$ref\": \"#/$defs/JournalEntry\""]
#[doc = "      }"]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct HistoryPage {
    #[serde(default, skip_serializing_if = "::std::vec::Vec::is_empty")]
    pub entries: ::std::vec::Vec<JournalEntry>,
}
impl ::std::default::Default for HistoryPage {
    fn default() -> Self {
        Self {
            entries: Default::default(),
        }
    }
}
impl HistoryPage {
    pub fn builder() -> builder::HistoryPage {
        Default::default()
    }
}
#[doc = "What E.V. has done, newest first.\n\nA request rather than an event: history is asked for, not pushed. The\nanswer arrives in the response payload as `entries`, shaped like\n`JournalEntry` below."]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"HistoryQuery\","]
#[doc = "  \"description\": \"What E.V. has done, newest first.\\n\\nA request rather than an event: history is asked for, not pushed. The\\nanswer arrives in the response payload as `entries`, shaped like\\n`JournalEntry` below.\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"properties\": {"]
#[doc = "    \"before\": {"]
#[doc = "      \"title\": \"Before\","]
#[doc = "      \"description\": \"Only entries older than this id. For paging.\","]
#[doc = "      \"default\": null,"]
#[doc = "      \"anyOf\": ["]
#[doc = "        {"]
#[doc = "          \"type\": \"integer\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"type\": \"null\""]
#[doc = "        }"]
#[doc = "      ]"]
#[doc = "    },"]
#[doc = "    \"limit\": {"]
#[doc = "      \"title\": \"Limit\","]
#[doc = "      \"default\": 20,"]
#[doc = "      \"type\": \"integer\","]
#[doc = "      \"maximum\": 500.0,"]
#[doc = "      \"minimum\": 1.0"]
#[doc = "    },"]
#[doc = "    \"query\": {"]
#[doc = "      \"title\": \"Query\","]
#[doc = "      \"description\": \"Search the trail instead of paging it: a tool, an album, a note's title. Accents are folded. Ignores `before`, because a search is not a page.\","]
#[doc = "      \"default\": null,"]
#[doc = "      \"anyOf\": ["]
#[doc = "        {"]
#[doc = "          \"type\": \"string\","]
#[doc = "          \"maxLength\": 200"]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"type\": \"null\""]
#[doc = "        }"]
#[doc = "      ]"]
#[doc = "    },"]
#[doc = "    \"type\": {"]
#[doc = "      \"title\": \"Type\","]
#[doc = "      \"default\": \"history.query\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"const\": \"history.query\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct HistoryQuery {
    #[doc = "Only entries older than this id. For paging."]
    #[serde(default, skip_serializing_if = "::std::option::Option::is_none")]
    pub before: ::std::option::Option<i64>,
    #[serde(default = "defaults::default_nzu64::<::std::num::NonZeroU64, 20>")]
    pub limit: ::std::num::NonZeroU64,
    #[doc = "Search the trail instead of paging it: a tool, an album, a note's title. Accents are folded. Ignores `before`, because a search is not a page."]
    #[serde(default, skip_serializing_if = "::std::option::Option::is_none")]
    pub query: ::std::option::Option<HistoryQueryQuery>,
    #[serde(rename = "type", default = "defaults::history_query_type")]
    pub type_: ::std::string::String,
}
impl ::std::default::Default for HistoryQuery {
    fn default() -> Self {
        Self {
            before: Default::default(),
            limit: defaults::default_nzu64::<::std::num::NonZeroU64, 20>(),
            query: Default::default(),
            type_: defaults::history_query_type(),
        }
    }
}
impl HistoryQuery {
    pub fn builder() -> builder::HistoryQuery {
        Default::default()
    }
}
#[doc = "`HistoryQueryQuery`"]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"type\": \"string\","]
#[doc = "  \"maxLength\": 200"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Serialize, Clone, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
#[serde(transparent)]
pub struct HistoryQueryQuery(::std::string::String);
impl ::std::ops::Deref for HistoryQueryQuery {
    type Target = ::std::string::String;
    fn deref(&self) -> &::std::string::String {
        &self.0
    }
}
impl ::std::convert::From<HistoryQueryQuery> for ::std::string::String {
    fn from(value: HistoryQueryQuery) -> Self {
        value.0
    }
}
impl ::std::str::FromStr for HistoryQueryQuery {
    type Err = self::error::ConversionError;
    fn from_str(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        if value.chars().count() > 200usize {
            return Err("longer than 200 characters".into());
        }
        Ok(Self(value.to_string()))
    }
}
impl ::std::convert::TryFrom<&str> for HistoryQueryQuery {
    type Error = self::error::ConversionError;
    fn try_from(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<&::std::string::String> for HistoryQueryQuery {
    type Error = self::error::ConversionError;
    fn try_from(
        value: &::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<::std::string::String> for HistoryQueryQuery {
    type Error = self::error::ConversionError;
    fn try_from(
        value: ::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl<'de> ::serde::Deserialize<'de> for HistoryQueryQuery {
    fn deserialize<D>(deserializer: D) -> ::std::result::Result<Self, D::Error>
    where
        D: ::serde::Deserializer<'de>,
    {
        ::std::string::String::deserialize(deserializer)?
            .parse()
            .map_err(|e: self::error::ConversionError| {
                <D::Error as ::serde::de::Error>::custom(e.to_string())
            })
    }
}
#[doc = "base64 of a JPEG or PNG frame."]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"Image\","]
#[doc = "  \"description\": \"base64 of a JPEG or PNG frame.\","]
#[doc = "  \"type\": \"string\","]
#[doc = "  \"maxLength\": 8000000"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Serialize, Clone, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
#[serde(transparent)]
pub struct Image(::std::string::String);
impl ::std::ops::Deref for Image {
    type Target = ::std::string::String;
    fn deref(&self) -> &::std::string::String {
        &self.0
    }
}
impl ::std::convert::From<Image> for ::std::string::String {
    fn from(value: Image) -> Self {
        value.0
    }
}
impl ::std::str::FromStr for Image {
    type Err = self::error::ConversionError;
    fn from_str(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        if value.chars().count() > 8000000usize {
            return Err("longer than 8000000 characters".into());
        }
        Ok(Self(value.to_string()))
    }
}
impl ::std::convert::TryFrom<&str> for Image {
    type Error = self::error::ConversionError;
    fn try_from(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<&::std::string::String> for Image {
    type Error = self::error::ConversionError;
    fn try_from(
        value: &::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<::std::string::String> for Image {
    type Error = self::error::ConversionError;
    fn try_from(
        value: ::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl<'de> ::serde::Deserialize<'de> for Image {
    fn deserialize<D>(deserializer: D) -> ::std::result::Result<Self, D::Error>
    where
        D: ::serde::Deserializer<'de>,
    {
        ::std::string::String::deserialize(deserializer)?
            .parse()
            .map_err(|e: self::error::ConversionError| {
                <D::Error as ::serde::de::Error>::custom(e.to_string())
            })
    }
}
#[doc = "What E.V. did, once."]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"JournalEntry\","]
#[doc = "  \"description\": \"What E.V. did, once.\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"required\": ["]
#[doc = "    \"id\","]
#[doc = "    \"ok\","]
#[doc = "    \"recorded_at\","]
#[doc = "    \"risk\","]
#[doc = "    \"tool\""]
#[doc = "  ],"]
#[doc = "  \"properties\": {"]
#[doc = "    \"arguments\": {"]
#[doc = "      \"title\": \"Arguments\","]
#[doc = "      \"type\": \"object\","]
#[doc = "      \"additionalProperties\": true"]
#[doc = "    },"]
#[doc = "    \"error_code\": {"]
#[doc = "      \"title\": \"Error Code\","]
#[doc = "      \"default\": null,"]
#[doc = "      \"anyOf\": ["]
#[doc = "        {"]
#[doc = "          \"type\": \"string\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"type\": \"null\""]
#[doc = "        }"]
#[doc = "      ]"]
#[doc = "    },"]
#[doc = "    \"error_message\": {"]
#[doc = "      \"title\": \"Error Message\","]
#[doc = "      \"default\": null,"]
#[doc = "      \"anyOf\": ["]
#[doc = "        {"]
#[doc = "          \"type\": \"string\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"type\": \"null\""]
#[doc = "        }"]
#[doc = "      ]"]
#[doc = "    },"]
#[doc = "    \"id\": {"]
#[doc = "      \"title\": \"Id\","]
#[doc = "      \"type\": \"integer\""]
#[doc = "    },"]
#[doc = "    \"ok\": {"]
#[doc = "      \"title\": \"Ok\","]
#[doc = "      \"type\": \"boolean\""]
#[doc = "    },"]
#[doc = "    \"recorded_at\": {"]
#[doc = "      \"title\": \"Recorded At\","]
#[doc = "      \"description\": \"ISO 8601, UTC, stamped when it happened.\","]
#[doc = "      \"type\": \"string\""]
#[doc = "    },"]
#[doc = "    \"risk\": {"]
#[doc = "      \"$ref\": \"#/$defs/RiskLevel\""]
#[doc = "    },"]
#[doc = "    \"speech\": {"]
#[doc = "      \"title\": \"Speech\","]
#[doc = "      \"default\": null,"]
#[doc = "      \"anyOf\": ["]
#[doc = "        {"]
#[doc = "          \"type\": \"string\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"type\": \"null\""]
#[doc = "        }"]
#[doc = "      ]"]
#[doc = "    },"]
#[doc = "    \"tool\": {"]
#[doc = "      \"title\": \"Tool\","]
#[doc = "      \"type\": \"string\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct JournalEntry {
    #[serde(default, skip_serializing_if = "::serde_json::Map::is_empty")]
    pub arguments: ::serde_json::Map<::std::string::String, ::serde_json::Value>,
    #[serde(default, skip_serializing_if = "::std::option::Option::is_none")]
    pub error_code: ::std::option::Option<::std::string::String>,
    #[serde(default, skip_serializing_if = "::std::option::Option::is_none")]
    pub error_message: ::std::option::Option<::std::string::String>,
    pub id: i64,
    pub ok: bool,
    #[doc = "ISO 8601, UTC, stamped when it happened."]
    pub recorded_at: ::std::string::String,
    pub risk: RiskLevel,
    #[serde(default, skip_serializing_if = "::std::option::Option::is_none")]
    pub speech: ::std::option::Option<::std::string::String>,
    pub tool: ::std::string::String,
}
impl JournalEntry {
    pub fn builder() -> builder::JournalEntry {
        Default::default()
    }
}
#[doc = "A capability macOS gates behind TCC."]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"Permission\","]
#[doc = "  \"description\": \"A capability macOS gates behind TCC.\","]
#[doc = "  \"type\": \"string\","]
#[doc = "  \"enum\": ["]
#[doc = "    \"microphone\","]
#[doc = "    \"camera\","]
#[doc = "    \"accessibility\","]
#[doc = "    \"apple_events\""]
#[doc = "  ]"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(
    :: serde :: Deserialize,
    :: serde :: Serialize,
    Clone,
    Copy,
    Debug,
    Eq,
    Hash,
    Ord,
    PartialEq,
    PartialOrd,
)]
pub enum Permission {
    #[serde(rename = "microphone")]
    Microphone,
    #[serde(rename = "camera")]
    Camera,
    #[serde(rename = "accessibility")]
    Accessibility,
    #[serde(rename = "apple_events")]
    AppleEvents,
}
impl ::std::fmt::Display for Permission {
    fn fmt(&self, f: &mut ::std::fmt::Formatter<'_>) -> ::std::fmt::Result {
        match *self {
            Self::Microphone => f.write_str("microphone"),
            Self::Camera => f.write_str("camera"),
            Self::Accessibility => f.write_str("accessibility"),
            Self::AppleEvents => f.write_str("apple_events"),
        }
    }
}
impl ::std::str::FromStr for Permission {
    type Err = self::error::ConversionError;
    fn from_str(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        match value {
            "microphone" => Ok(Self::Microphone),
            "camera" => Ok(Self::Camera),
            "accessibility" => Ok(Self::Accessibility),
            "apple_events" => Ok(Self::AppleEvents),
            _ => Err("invalid value".into()),
        }
    }
}
impl ::std::convert::TryFrom<&str> for Permission {
    type Error = self::error::ConversionError;
    fn try_from(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<&::std::string::String> for Permission {
    type Error = self::error::ConversionError;
    fn try_from(
        value: &::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<::std::string::String> for Permission {
    type Error = self::error::ConversionError;
    fn try_from(
        value: ::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
#[doc = "The native host reporting what macOS says. The Python core never infers\nthis (invariant 7); it only ever learns it here."]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"PermissionChanged\","]
#[doc = "  \"description\": \"The native host reporting what macOS says. The Python core never infers\\nthis (invariant 7); it only ever learns it here.\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"required\": ["]
#[doc = "    \"permission\","]
#[doc = "    \"state\""]
#[doc = "  ],"]
#[doc = "  \"properties\": {"]
#[doc = "    \"permission\": {"]
#[doc = "      \"$ref\": \"#/$defs/Permission\""]
#[doc = "    },"]
#[doc = "    \"state\": {"]
#[doc = "      \"$ref\": \"#/$defs/PermissionState\""]
#[doc = "    },"]
#[doc = "    \"type\": {"]
#[doc = "      \"title\": \"Type\","]
#[doc = "      \"default\": \"permission.changed\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"const\": \"permission.changed\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct PermissionChanged {
    pub permission: Permission,
    pub state: PermissionState,
    #[serde(rename = "type", default = "defaults::permission_changed_type")]
    pub type_: ::std::string::String,
}
impl PermissionChanged {
    pub fn builder() -> builder::PermissionChanged {
        Default::default()
    }
}
#[doc = "What macOS said about a permission, from the process it said it to.\n\nInvariant 7: permission state is reported by the signed host, never\ninferred by the core. This is that report. Only the host can know whether\na camera opened or a microphone was refused, because it is the process\nmacOS answered.\n\nSent when there is evidence -- a device that opened, a prompt that was\nanswered -- and not on a schedule. A permission nobody has exercised is\n`undetermined`, which is a true statement rather than a missing one."]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"PermissionReport\","]
#[doc = "  \"description\": \"What macOS said about a permission, from the process it said it to.\\n\\nInvariant 7: permission state is reported by the signed host, never\\ninferred by the core. This is that report. Only the host can know whether\\na camera opened or a microphone was refused, because it is the process\\nmacOS answered.\\n\\nSent when there is evidence -- a device that opened, a prompt that was\\nanswered -- and not on a schedule. A permission nobody has exercised is\\n`undetermined`, which is a true statement rather than a missing one.\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"required\": ["]
#[doc = "    \"permission\","]
#[doc = "    \"state\""]
#[doc = "  ],"]
#[doc = "  \"properties\": {"]
#[doc = "    \"permission\": {"]
#[doc = "      \"$ref\": \"#/$defs/Permission\""]
#[doc = "    },"]
#[doc = "    \"state\": {"]
#[doc = "      \"$ref\": \"#/$defs/PermissionState\""]
#[doc = "    },"]
#[doc = "    \"type\": {"]
#[doc = "      \"title\": \"Type\","]
#[doc = "      \"default\": \"permission.report\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"const\": \"permission.report\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct PermissionReport {
    pub permission: Permission,
    pub state: PermissionState,
    #[serde(rename = "type", default = "defaults::permission_report_type")]
    pub type_: ::std::string::String,
}
impl PermissionReport {
    pub fn builder() -> builder::PermissionReport {
        Default::default()
    }
}
#[doc = "What the host last reported for a permission."]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"PermissionState\","]
#[doc = "  \"description\": \"What the host last reported for a permission.\","]
#[doc = "  \"type\": \"string\","]
#[doc = "  \"enum\": ["]
#[doc = "    \"granted\","]
#[doc = "    \"denied\","]
#[doc = "    \"undetermined\""]
#[doc = "  ]"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(
    :: serde :: Deserialize,
    :: serde :: Serialize,
    Clone,
    Copy,
    Debug,
    Eq,
    Hash,
    Ord,
    PartialEq,
    PartialOrd,
)]
pub enum PermissionState {
    #[serde(rename = "granted")]
    Granted,
    #[serde(rename = "denied")]
    Denied,
    #[serde(rename = "undetermined")]
    Undetermined,
}
impl ::std::fmt::Display for PermissionState {
    fn fmt(&self, f: &mut ::std::fmt::Formatter<'_>) -> ::std::fmt::Result {
        match *self {
            Self::Granted => f.write_str("granted"),
            Self::Denied => f.write_str("denied"),
            Self::Undetermined => f.write_str("undetermined"),
        }
    }
}
impl ::std::str::FromStr for PermissionState {
    type Err = self::error::ConversionError;
    fn from_str(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        match value {
            "granted" => Ok(Self::Granted),
            "denied" => Ok(Self::Denied),
            "undetermined" => Ok(Self::Undetermined),
            _ => Err("invalid value".into()),
        }
    }
}
impl ::std::convert::TryFrom<&str> for PermissionState {
    type Error = self::error::ConversionError;
    fn try_from(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<&::std::string::String> for PermissionState {
    type Error = self::error::ConversionError;
    fn try_from(
        value: &::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<::std::string::String> for PermissionState {
    type Error = self::error::ConversionError;
    fn try_from(
        value: ::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
#[doc = "A command with an id. Exactly one `Response` carries the same id back."]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"Request\","]
#[doc = "  \"description\": \"A command with an id. Exactly one `Response` carries the same id back.\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"required\": ["]
#[doc = "    \"command\","]
#[doc = "    \"id\""]
#[doc = "  ],"]
#[doc = "  \"properties\": {"]
#[doc = "    \"command\": {"]
#[doc = "      \"title\": \"Command\","]
#[doc = "      \"oneOf\": ["]
#[doc = "        {"]
#[doc = "          \"$ref\": \"#/$defs/Hello\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"$ref\": \"#/$defs/UtteranceSubmit\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"$ref\": \"#/$defs/AudioSubmit\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"$ref\": \"#/$defs/VisionSubmit\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"$ref\": \"#/$defs/ConfirmationRespond\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"$ref\": \"#/$defs/HistoryQuery\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"$ref\": \"#/$defs/PermissionReport\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"$ref\": \"#/$defs/SessionCancel\""]
#[doc = "        }"]
#[doc = "      ],"]
#[doc = "      \"discriminator\": {"]
#[doc = "        \"mapping\": {"]
#[doc = "          \"audio.submit\": \"#/$defs/AudioSubmit\","]
#[doc = "          \"confirmation.respond\": \"#/$defs/ConfirmationRespond\","]
#[doc = "          \"hello\": \"#/$defs/Hello\","]
#[doc = "          \"history.query\": \"#/$defs/HistoryQuery\","]
#[doc = "          \"permission.report\": \"#/$defs/PermissionReport\","]
#[doc = "          \"session.cancel\": \"#/$defs/SessionCancel\","]
#[doc = "          \"utterance.submit\": \"#/$defs/UtteranceSubmit\","]
#[doc = "          \"vision.submit\": \"#/$defs/VisionSubmit\""]
#[doc = "        },"]
#[doc = "        \"propertyName\": \"type\""]
#[doc = "      }"]
#[doc = "    },"]
#[doc = "    \"id\": {"]
#[doc = "      \"title\": \"Id\","]
#[doc = "      \"type\": \"string\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub command: Command,
    pub id: ::std::string::String,
}
impl Request {
    pub fn builder() -> builder::Request {
        Default::default()
    }
}
#[doc = "`Response`"]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"Response\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"required\": ["]
#[doc = "    \"id\","]
#[doc = "    \"ok\""]
#[doc = "  ],"]
#[doc = "  \"properties\": {"]
#[doc = "    \"error\": {"]
#[doc = "      \"default\": null,"]
#[doc = "      \"anyOf\": ["]
#[doc = "        {"]
#[doc = "          \"$ref\": \"#/$defs/ResponseError\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"type\": \"null\""]
#[doc = "        }"]
#[doc = "      ]"]
#[doc = "    },"]
#[doc = "    \"id\": {"]
#[doc = "      \"title\": \"Id\","]
#[doc = "      \"type\": \"string\""]
#[doc = "    },"]
#[doc = "    \"ok\": {"]
#[doc = "      \"title\": \"Ok\","]
#[doc = "      \"type\": \"boolean\""]
#[doc = "    },"]
#[doc = "    \"payload\": {"]
#[doc = "      \"title\": \"Payload\","]
#[doc = "      \"type\": \"object\","]
#[doc = "      \"additionalProperties\": true"]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct Response {
    #[serde(default, skip_serializing_if = "::std::option::Option::is_none")]
    pub error: ::std::option::Option<ResponseError>,
    pub id: ::std::string::String,
    pub ok: bool,
    #[serde(default, skip_serializing_if = "::serde_json::Map::is_empty")]
    pub payload: ::serde_json::Map<::std::string::String, ::serde_json::Value>,
}
impl Response {
    pub fn builder() -> builder::Response {
        Default::default()
    }
}
#[doc = "`ResponseError`"]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"ResponseError\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"required\": ["]
#[doc = "    \"code\","]
#[doc = "    \"message\""]
#[doc = "  ],"]
#[doc = "  \"properties\": {"]
#[doc = "    \"code\": {"]
#[doc = "      \"title\": \"Code\","]
#[doc = "      \"type\": \"string\""]
#[doc = "    },"]
#[doc = "    \"message\": {"]
#[doc = "      \"title\": \"Message\","]
#[doc = "      \"type\": \"string\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct ResponseError {
    pub code: ::std::string::String,
    pub message: ::std::string::String,
}
impl ResponseError {
    pub fn builder() -> builder::ResponseError {
        Default::default()
    }
}
#[doc = "Declared per tool in `tools.py`, never inferred from the arguments."]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"RiskLevel\","]
#[doc = "  \"description\": \"Declared per tool in `tools.py`, never inferred from the arguments.\","]
#[doc = "  \"type\": \"string\","]
#[doc = "  \"enum\": ["]
#[doc = "    \"safe\","]
#[doc = "    \"sensitive\","]
#[doc = "    \"destructive\""]
#[doc = "  ]"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(
    :: serde :: Deserialize,
    :: serde :: Serialize,
    Clone,
    Copy,
    Debug,
    Eq,
    Hash,
    Ord,
    PartialEq,
    PartialOrd,
)]
pub enum RiskLevel {
    #[serde(rename = "safe")]
    Safe,
    #[serde(rename = "sensitive")]
    Sensitive,
    #[serde(rename = "destructive")]
    Destructive,
}
impl ::std::fmt::Display for RiskLevel {
    fn fmt(&self, f: &mut ::std::fmt::Formatter<'_>) -> ::std::fmt::Result {
        match *self {
            Self::Safe => f.write_str("safe"),
            Self::Sensitive => f.write_str("sensitive"),
            Self::Destructive => f.write_str("destructive"),
        }
    }
}
impl ::std::str::FromStr for RiskLevel {
    type Err = self::error::ConversionError;
    fn from_str(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        match value {
            "safe" => Ok(Self::Safe),
            "sensitive" => Ok(Self::Sensitive),
            "destructive" => Ok(Self::Destructive),
            _ => Err("invalid value".into()),
        }
    }
}
impl ::std::convert::TryFrom<&str> for RiskLevel {
    type Error = self::error::ConversionError;
    fn try_from(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<&::std::string::String> for RiskLevel {
    type Error = self::error::ConversionError;
    fn try_from(
        value: &::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<::std::string::String> for RiskLevel {
    type Error = self::error::ConversionError;
    fn try_from(
        value: ::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
#[doc = "`SessionCancel`"]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"SessionCancel\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"properties\": {"]
#[doc = "    \"type\": {"]
#[doc = "      \"title\": \"Type\","]
#[doc = "      \"default\": \"session.cancel\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"const\": \"session.cancel\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct SessionCancel {
    #[serde(rename = "type", default = "defaults::session_cancel_type")]
    pub type_: ::std::string::String,
}
impl ::std::default::Default for SessionCancel {
    fn default() -> Self {
        Self {
            type_: defaults::session_cancel_type(),
        }
    }
}
impl SessionCancel {
    pub fn builder() -> builder::SessionCancel {
        Default::default()
    }
}
#[doc = "Intent, not audio. The native layer owns the device."]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"SpeechRequested\","]
#[doc = "  \"description\": \"Intent, not audio. The native layer owns the device.\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"required\": ["]
#[doc = "    \"text\","]
#[doc = "    \"voice\""]
#[doc = "  ],"]
#[doc = "  \"properties\": {"]
#[doc = "    \"interrupt\": {"]
#[doc = "      \"title\": \"Interrupt\","]
#[doc = "      \"default\": false,"]
#[doc = "      \"type\": \"boolean\""]
#[doc = "    },"]
#[doc = "    \"text\": {"]
#[doc = "      \"title\": \"Text\","]
#[doc = "      \"type\": \"string\""]
#[doc = "    },"]
#[doc = "    \"type\": {"]
#[doc = "      \"title\": \"Type\","]
#[doc = "      \"default\": \"speech.requested\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"const\": \"speech.requested\""]
#[doc = "    },"]
#[doc = "    \"voice\": {"]
#[doc = "      \"title\": \"Voice\","]
#[doc = "      \"description\": \"A locale, e.g. pt-PT.\","]
#[doc = "      \"type\": \"string\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct SpeechRequested {
    #[serde(default)]
    pub interrupt: bool,
    pub text: ::std::string::String,
    #[serde(rename = "type", default = "defaults::speech_requested_type")]
    pub type_: ::std::string::String,
    #[doc = "A locale, e.g. pt-PT."]
    pub voice: ::std::string::String,
}
impl SpeechRequested {
    pub fn builder() -> builder::SpeechRequested {
        Default::default()
    }
}
#[doc = "`State`"]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"State\","]
#[doc = "  \"type\": \"string\","]
#[doc = "  \"enum\": ["]
#[doc = "    \"idle\","]
#[doc = "    \"listening\","]
#[doc = "    \"thinking\","]
#[doc = "    \"acting\","]
#[doc = "    \"speaking\""]
#[doc = "  ]"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(
    :: serde :: Deserialize,
    :: serde :: Serialize,
    Clone,
    Copy,
    Debug,
    Eq,
    Hash,
    Ord,
    PartialEq,
    PartialOrd,
)]
pub enum State {
    #[serde(rename = "idle")]
    Idle,
    #[serde(rename = "listening")]
    Listening,
    #[serde(rename = "thinking")]
    Thinking,
    #[serde(rename = "acting")]
    Acting,
    #[serde(rename = "speaking")]
    Speaking,
}
impl ::std::fmt::Display for State {
    fn fmt(&self, f: &mut ::std::fmt::Formatter<'_>) -> ::std::fmt::Result {
        match *self {
            Self::Idle => f.write_str("idle"),
            Self::Listening => f.write_str("listening"),
            Self::Thinking => f.write_str("thinking"),
            Self::Acting => f.write_str("acting"),
            Self::Speaking => f.write_str("speaking"),
        }
    }
}
impl ::std::str::FromStr for State {
    type Err = self::error::ConversionError;
    fn from_str(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        match value {
            "idle" => Ok(Self::Idle),
            "listening" => Ok(Self::Listening),
            "thinking" => Ok(Self::Thinking),
            "acting" => Ok(Self::Acting),
            "speaking" => Ok(Self::Speaking),
            _ => Err("invalid value".into()),
        }
    }
}
impl ::std::convert::TryFrom<&str> for State {
    type Error = self::error::ConversionError;
    fn try_from(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<&::std::string::String> for State {
    type Error = self::error::ConversionError;
    fn try_from(
        value: &::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<::std::string::String> for State {
    type Error = self::error::ConversionError;
    fn try_from(
        value: ::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
#[doc = "`StateChanged`"]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"StateChanged\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"required\": ["]
#[doc = "    \"state\""]
#[doc = "  ],"]
#[doc = "  \"properties\": {"]
#[doc = "    \"state\": {"]
#[doc = "      \"title\": \"State\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"enum\": ["]
#[doc = "        \"idle\","]
#[doc = "        \"listening\","]
#[doc = "        \"thinking\","]
#[doc = "        \"acting\","]
#[doc = "        \"speaking\""]
#[doc = "      ]"]
#[doc = "    },"]
#[doc = "    \"type\": {"]
#[doc = "      \"title\": \"Type\","]
#[doc = "      \"default\": \"state.changed\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"const\": \"state.changed\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct StateChanged {
    pub state: State,
    #[serde(rename = "type", default = "defaults::state_changed_type")]
    pub type_: ::std::string::String,
}
impl StateChanged {
    pub fn builder() -> builder::StateChanged {
        Default::default()
    }
}
#[doc = "`Text`"]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"Text\","]
#[doc = "  \"type\": \"string\","]
#[doc = "  \"maxLength\": 4000,"]
#[doc = "  \"minLength\": 1"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Serialize, Clone, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
#[serde(transparent)]
pub struct Text(::std::string::String);
impl ::std::ops::Deref for Text {
    type Target = ::std::string::String;
    fn deref(&self) -> &::std::string::String {
        &self.0
    }
}
impl ::std::convert::From<Text> for ::std::string::String {
    fn from(value: Text) -> Self {
        value.0
    }
}
impl ::std::str::FromStr for Text {
    type Err = self::error::ConversionError;
    fn from_str(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        if value.chars().count() > 4000usize {
            return Err("longer than 4000 characters".into());
        }
        if value.chars().count() < 1usize {
            return Err("shorter than 1 characters".into());
        }
        Ok(Self(value.to_string()))
    }
}
impl ::std::convert::TryFrom<&str> for Text {
    type Error = self::error::ConversionError;
    fn try_from(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<&::std::string::String> for Text {
    type Error = self::error::ConversionError;
    fn try_from(
        value: &::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<::std::string::String> for Text {
    type Error = self::error::ConversionError;
    fn try_from(
        value: ::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl<'de> ::serde::Deserialize<'de> for Text {
    fn deserialize<D>(deserializer: D) -> ::std::result::Result<Self, D::Error>
    where
        D: ::serde::Deserializer<'de>,
    {
        ::std::string::String::deserialize(deserializer)?
            .parse()
            .map_err(|e: self::error::ConversionError| {
                <D::Error as ::serde::de::Error>::custom(e.to_string())
            })
    }
}
#[doc = "`ToolCompleted`"]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"ToolCompleted\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"required\": ["]
#[doc = "    \"ok\","]
#[doc = "    \"tool\""]
#[doc = "  ],"]
#[doc = "  \"properties\": {"]
#[doc = "    \"error\": {"]
#[doc = "      \"title\": \"Error\","]
#[doc = "      \"default\": null,"]
#[doc = "      \"anyOf\": ["]
#[doc = "        {"]
#[doc = "          \"type\": \"string\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"type\": \"null\""]
#[doc = "        }"]
#[doc = "      ]"]
#[doc = "    },"]
#[doc = "    \"ok\": {"]
#[doc = "      \"title\": \"Ok\","]
#[doc = "      \"type\": \"boolean\""]
#[doc = "    },"]
#[doc = "    \"speech\": {"]
#[doc = "      \"title\": \"Speech\","]
#[doc = "      \"default\": null,"]
#[doc = "      \"anyOf\": ["]
#[doc = "        {"]
#[doc = "          \"type\": \"string\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"type\": \"null\""]
#[doc = "        }"]
#[doc = "      ]"]
#[doc = "    },"]
#[doc = "    \"tool\": {"]
#[doc = "      \"title\": \"Tool\","]
#[doc = "      \"type\": \"string\""]
#[doc = "    },"]
#[doc = "    \"type\": {"]
#[doc = "      \"title\": \"Type\","]
#[doc = "      \"default\": \"tool.completed\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"const\": \"tool.completed\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct ToolCompleted {
    #[serde(default, skip_serializing_if = "::std::option::Option::is_none")]
    pub error: ::std::option::Option<::std::string::String>,
    pub ok: bool,
    #[serde(default, skip_serializing_if = "::std::option::Option::is_none")]
    pub speech: ::std::option::Option<::std::string::String>,
    pub tool: ::std::string::String,
    #[serde(rename = "type", default = "defaults::tool_completed_type")]
    pub type_: ::std::string::String,
}
impl ToolCompleted {
    pub fn builder() -> builder::ToolCompleted {
        Default::default()
    }
}
#[doc = "`TranscriptionPartial`"]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"TranscriptionPartial\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"required\": ["]
#[doc = "    \"text\""]
#[doc = "  ],"]
#[doc = "  \"properties\": {"]
#[doc = "    \"text\": {"]
#[doc = "      \"title\": \"Text\","]
#[doc = "      \"type\": \"string\""]
#[doc = "    },"]
#[doc = "    \"type\": {"]
#[doc = "      \"title\": \"Type\","]
#[doc = "      \"default\": \"transcription.partial\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"const\": \"transcription.partial\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct TranscriptionPartial {
    pub text: ::std::string::String,
    #[serde(rename = "type", default = "defaults::transcription_partial_type")]
    pub type_: ::std::string::String,
}
impl TranscriptionPartial {
    pub fn builder() -> builder::TranscriptionPartial {
        Default::default()
    }
}
#[doc = "`UtteranceSubmit`"]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"UtteranceSubmit\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"required\": ["]
#[doc = "    \"text\""]
#[doc = "  ],"]
#[doc = "  \"properties\": {"]
#[doc = "    \"locale\": {"]
#[doc = "      \"title\": \"Locale\","]
#[doc = "      \"description\": \"The session locale, e.g. pt-PT. Carried, never used to translate the utterance before routing.\","]
#[doc = "      \"default\": null,"]
#[doc = "      \"anyOf\": ["]
#[doc = "        {"]
#[doc = "          \"type\": \"string\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"type\": \"null\""]
#[doc = "        }"]
#[doc = "      ]"]
#[doc = "    },"]
#[doc = "    \"text\": {"]
#[doc = "      \"title\": \"Text\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"maxLength\": 4000,"]
#[doc = "      \"minLength\": 1"]
#[doc = "    },"]
#[doc = "    \"type\": {"]
#[doc = "      \"title\": \"Type\","]
#[doc = "      \"default\": \"utterance.submit\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"const\": \"utterance.submit\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct UtteranceSubmit {
    #[doc = "The session locale, e.g. pt-PT. Carried, never used to translate the utterance before routing."]
    #[serde(default, skip_serializing_if = "::std::option::Option::is_none")]
    pub locale: ::std::option::Option<::std::string::String>,
    pub text: Text,
    #[serde(rename = "type", default = "defaults::utterance_submit_type")]
    pub type_: ::std::string::String,
}
impl UtteranceSubmit {
    pub fn builder() -> builder::UtteranceSubmit {
        Default::default()
    }
}
#[doc = "One frame, and optionally what to ask about it.\n\nThe same shape as `audio.submit` and for the same reason: a surface\ncaptured it because a person asked for it. `CLAUDE.md` invariant 8 -- the\ncamera may not be started by ambiguous model inference -- is why a frame\narrives as a command rather than being fetched by a tool.\n\nNothing here names a file. The frame crosses as bytes, is answered, and is\nnot persisted."]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"title\": \"VisionSubmit\","]
#[doc = "  \"description\": \"One frame, and optionally what to ask about it.\\n\\nThe same shape as `audio.submit` and for the same reason: a surface\\ncaptured it because a person asked for it. `CLAUDE.md` invariant 8 -- the\\ncamera may not be started by ambiguous model inference -- is why a frame\\narrives as a command rather than being fetched by a tool.\\n\\nNothing here names a file. The frame crosses as bytes, is answered, and is\\nnot persisted.\","]
#[doc = "  \"type\": \"object\","]
#[doc = "  \"required\": ["]
#[doc = "    \"image\""]
#[doc = "  ],"]
#[doc = "  \"properties\": {"]
#[doc = "    \"image\": {"]
#[doc = "      \"title\": \"Image\","]
#[doc = "      \"description\": \"base64 of a JPEG or PNG frame.\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"maxLength\": 8000000"]
#[doc = "    },"]
#[doc = "    \"locale\": {"]
#[doc = "      \"title\": \"Locale\","]
#[doc = "      \"description\": \"The session locale.\","]
#[doc = "      \"default\": null,"]
#[doc = "      \"anyOf\": ["]
#[doc = "        {"]
#[doc = "          \"type\": \"string\""]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"type\": \"null\""]
#[doc = "        }"]
#[doc = "      ]"]
#[doc = "    },"]
#[doc = "    \"text\": {"]
#[doc = "      \"title\": \"Text\","]
#[doc = "      \"description\": \"What was said while looking, verbatim. Absent means: describe it.\","]
#[doc = "      \"default\": null,"]
#[doc = "      \"anyOf\": ["]
#[doc = "        {"]
#[doc = "          \"type\": \"string\","]
#[doc = "          \"maxLength\": 4000"]
#[doc = "        },"]
#[doc = "        {"]
#[doc = "          \"type\": \"null\""]
#[doc = "        }"]
#[doc = "      ]"]
#[doc = "    },"]
#[doc = "    \"type\": {"]
#[doc = "      \"title\": \"Type\","]
#[doc = "      \"default\": \"vision.submit\","]
#[doc = "      \"type\": \"string\","]
#[doc = "      \"const\": \"vision.submit\""]
#[doc = "    }"]
#[doc = "  },"]
#[doc = "  \"additionalProperties\": false"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Deserialize, :: serde :: Serialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct VisionSubmit {
    #[doc = "base64 of a JPEG or PNG frame."]
    pub image: Image,
    #[doc = "The session locale."]
    #[serde(default, skip_serializing_if = "::std::option::Option::is_none")]
    pub locale: ::std::option::Option<::std::string::String>,
    #[doc = "What was said while looking, verbatim. Absent means: describe it."]
    #[serde(default, skip_serializing_if = "::std::option::Option::is_none")]
    pub text: ::std::option::Option<VisionSubmitText>,
    #[serde(rename = "type", default = "defaults::vision_submit_type")]
    pub type_: ::std::string::String,
}
impl VisionSubmit {
    pub fn builder() -> builder::VisionSubmit {
        Default::default()
    }
}
#[doc = "`VisionSubmitText`"]
#[doc = r""]
#[doc = r" <details><summary>JSON schema</summary>"]
#[doc = r""]
#[doc = r" ```json"]
#[doc = "{"]
#[doc = "  \"type\": \"string\","]
#[doc = "  \"maxLength\": 4000"]
#[doc = "}"]
#[doc = r" ```"]
#[doc = r" </details>"]
#[derive(:: serde :: Serialize, Clone, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
#[serde(transparent)]
pub struct VisionSubmitText(::std::string::String);
impl ::std::ops::Deref for VisionSubmitText {
    type Target = ::std::string::String;
    fn deref(&self) -> &::std::string::String {
        &self.0
    }
}
impl ::std::convert::From<VisionSubmitText> for ::std::string::String {
    fn from(value: VisionSubmitText) -> Self {
        value.0
    }
}
impl ::std::str::FromStr for VisionSubmitText {
    type Err = self::error::ConversionError;
    fn from_str(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        if value.chars().count() > 4000usize {
            return Err("longer than 4000 characters".into());
        }
        Ok(Self(value.to_string()))
    }
}
impl ::std::convert::TryFrom<&str> for VisionSubmitText {
    type Error = self::error::ConversionError;
    fn try_from(value: &str) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<&::std::string::String> for VisionSubmitText {
    type Error = self::error::ConversionError;
    fn try_from(
        value: &::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl ::std::convert::TryFrom<::std::string::String> for VisionSubmitText {
    type Error = self::error::ConversionError;
    fn try_from(
        value: ::std::string::String,
    ) -> ::std::result::Result<Self, self::error::ConversionError> {
        value.parse()
    }
}
impl<'de> ::serde::Deserialize<'de> for VisionSubmitText {
    fn deserialize<D>(deserializer: D) -> ::std::result::Result<Self, D::Error>
    where
        D: ::serde::Deserializer<'de>,
    {
        ::std::string::String::deserialize(deserializer)?
            .parse()
            .map_err(|e: self::error::ConversionError| {
                <D::Error as ::serde::de::Error>::custom(e.to_string())
            })
    }
}
#[doc = r" Types for composing complex structures."]
pub mod builder {
    #[derive(Clone, Debug)]
    pub struct AudioSubmit {
        audio: ::std::result::Result<super::Audio, ::std::string::String>,
        locale: ::std::result::Result<
            ::std::option::Option<::std::string::String>,
            ::std::string::String,
        >,
        sample_rate: ::std::result::Result<i64, ::std::string::String>,
        type_: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for AudioSubmit {
        fn default() -> Self {
            Self {
                audio: Err("no value supplied for audio".to_string()),
                locale: Ok(Default::default()),
                sample_rate: Ok(super::defaults::default_u64::<i64, 16000>()),
                type_: Ok(super::defaults::audio_submit_type()),
            }
        }
    }
    impl AudioSubmit {
        pub fn audio<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<super::Audio>,
            T::Error: ::std::fmt::Display,
        {
            self.audio = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for audio: {e}"));
            self
        }
        pub fn locale<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::option::Option<::std::string::String>>,
            T::Error: ::std::fmt::Display,
        {
            self.locale = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for locale: {e}"));
            self
        }
        pub fn sample_rate<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<i64>,
            T::Error: ::std::fmt::Display,
        {
            self.sample_rate = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for sample_rate: {e}"));
            self
        }
        pub fn type_<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.type_ = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for type_: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<AudioSubmit> for super::AudioSubmit {
        type Error = super::error::ConversionError;
        fn try_from(
            value: AudioSubmit,
        ) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                audio: value.audio?,
                locale: value.locale?,
                sample_rate: value.sample_rate?,
                type_: value.type_?,
            })
        }
    }
    impl ::std::convert::From<super::AudioSubmit> for AudioSubmit {
        fn from(value: super::AudioSubmit) -> Self {
            Self {
                audio: Ok(value.audio),
                locale: Ok(value.locale),
                sample_rate: Ok(value.sample_rate),
                type_: Ok(value.type_),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct ConfirmationRequired {
        arguments: ::std::result::Result<
            ::serde_json::Map<::std::string::String, ::serde_json::Value>,
            ::std::string::String,
        >,
        id: ::std::result::Result<::std::string::String, ::std::string::String>,
        risk: ::std::result::Result<super::RiskLevel, ::std::string::String>,
        tool: ::std::result::Result<::std::string::String, ::std::string::String>,
        type_: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for ConfirmationRequired {
        fn default() -> Self {
            Self {
                arguments: Ok(Default::default()),
                id: Err("no value supplied for id".to_string()),
                risk: Err("no value supplied for risk".to_string()),
                tool: Err("no value supplied for tool".to_string()),
                type_: Ok(super::defaults::confirmation_required_type()),
            }
        }
    }
    impl ConfirmationRequired {
        pub fn arguments<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<
                ::serde_json::Map<::std::string::String, ::serde_json::Value>,
            >,
            T::Error: ::std::fmt::Display,
        {
            self.arguments = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for arguments: {e}"));
            self
        }
        pub fn id<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.id = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for id: {e}"));
            self
        }
        pub fn risk<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<super::RiskLevel>,
            T::Error: ::std::fmt::Display,
        {
            self.risk = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for risk: {e}"));
            self
        }
        pub fn tool<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.tool = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for tool: {e}"));
            self
        }
        pub fn type_<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.type_ = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for type_: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<ConfirmationRequired> for super::ConfirmationRequired {
        type Error = super::error::ConversionError;
        fn try_from(
            value: ConfirmationRequired,
        ) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                arguments: value.arguments?,
                id: value.id?,
                risk: value.risk?,
                tool: value.tool?,
                type_: value.type_?,
            })
        }
    }
    impl ::std::convert::From<super::ConfirmationRequired> for ConfirmationRequired {
        fn from(value: super::ConfirmationRequired) -> Self {
            Self {
                arguments: Ok(value.arguments),
                id: Ok(value.id),
                risk: Ok(value.risk),
                tool: Ok(value.tool),
                type_: Ok(value.type_),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct ConfirmationRespond {
        granted: ::std::result::Result<bool, ::std::string::String>,
        request: ::std::result::Result<::std::string::String, ::std::string::String>,
        type_: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for ConfirmationRespond {
        fn default() -> Self {
            Self {
                granted: Err("no value supplied for granted".to_string()),
                request: Err("no value supplied for request".to_string()),
                type_: Ok(super::defaults::confirmation_respond_type()),
            }
        }
    }
    impl ConfirmationRespond {
        pub fn granted<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<bool>,
            T::Error: ::std::fmt::Display,
        {
            self.granted = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for granted: {e}"));
            self
        }
        pub fn request<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.request = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for request: {e}"));
            self
        }
        pub fn type_<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.type_ = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for type_: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<ConfirmationRespond> for super::ConfirmationRespond {
        type Error = super::error::ConversionError;
        fn try_from(
            value: ConfirmationRespond,
        ) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                granted: value.granted?,
                request: value.request?,
                type_: value.type_?,
            })
        }
    }
    impl ::std::convert::From<super::ConfirmationRespond> for ConfirmationRespond {
        fn from(value: super::ConfirmationRespond) -> Self {
            Self {
                granted: Ok(value.granted),
                request: Ok(value.request),
                type_: Ok(value.type_),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct Envelope {
        event: ::std::result::Result<
            ::std::option::Option<super::EnvelopeEvent>,
            ::std::string::String,
        >,
        page:
            ::std::result::Result<::std::option::Option<super::HistoryPage>, ::std::string::String>,
        request:
            ::std::result::Result<::std::option::Option<super::Request>, ::std::string::String>,
        response:
            ::std::result::Result<::std::option::Option<super::Response>, ::std::string::String>,
    }
    impl ::std::default::Default for Envelope {
        fn default() -> Self {
            Self {
                event: Ok(Default::default()),
                page: Ok(Default::default()),
                request: Ok(Default::default()),
                response: Ok(Default::default()),
            }
        }
    }
    impl Envelope {
        pub fn event<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::option::Option<super::EnvelopeEvent>>,
            T::Error: ::std::fmt::Display,
        {
            self.event = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for event: {e}"));
            self
        }
        pub fn page<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::option::Option<super::HistoryPage>>,
            T::Error: ::std::fmt::Display,
        {
            self.page = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for page: {e}"));
            self
        }
        pub fn request<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::option::Option<super::Request>>,
            T::Error: ::std::fmt::Display,
        {
            self.request = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for request: {e}"));
            self
        }
        pub fn response<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::option::Option<super::Response>>,
            T::Error: ::std::fmt::Display,
        {
            self.response = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for response: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<Envelope> for super::Envelope {
        type Error = super::error::ConversionError;
        fn try_from(value: Envelope) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                event: value.event?,
                page: value.page?,
                request: value.request?,
                response: value.response?,
            })
        }
    }
    impl ::std::convert::From<super::Envelope> for Envelope {
        fn from(value: super::Envelope) -> Self {
            Self {
                event: Ok(value.event),
                page: Ok(value.page),
                request: Ok(value.request),
                response: Ok(value.response),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct Hello {
        client: ::std::result::Result<::std::string::String, ::std::string::String>,
        protocol: ::std::result::Result<::std::string::String, ::std::string::String>,
        type_: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for Hello {
        fn default() -> Self {
            Self {
                client: Err("no value supplied for client".to_string()),
                protocol: Err("no value supplied for protocol".to_string()),
                type_: Ok(super::defaults::hello_type()),
            }
        }
    }
    impl Hello {
        pub fn client<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.client = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for client: {e}"));
            self
        }
        pub fn protocol<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.protocol = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for protocol: {e}"));
            self
        }
        pub fn type_<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.type_ = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for type_: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<Hello> for super::Hello {
        type Error = super::error::ConversionError;
        fn try_from(value: Hello) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                client: value.client?,
                protocol: value.protocol?,
                type_: value.type_?,
            })
        }
    }
    impl ::std::convert::From<super::Hello> for Hello {
        fn from(value: super::Hello) -> Self {
            Self {
                client: Ok(value.client),
                protocol: Ok(value.protocol),
                type_: Ok(value.type_),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct HistoryPage {
        entries: ::std::result::Result<::std::vec::Vec<super::JournalEntry>, ::std::string::String>,
    }
    impl ::std::default::Default for HistoryPage {
        fn default() -> Self {
            Self {
                entries: Ok(Default::default()),
            }
        }
    }
    impl HistoryPage {
        pub fn entries<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::vec::Vec<super::JournalEntry>>,
            T::Error: ::std::fmt::Display,
        {
            self.entries = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for entries: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<HistoryPage> for super::HistoryPage {
        type Error = super::error::ConversionError;
        fn try_from(
            value: HistoryPage,
        ) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                entries: value.entries?,
            })
        }
    }
    impl ::std::convert::From<super::HistoryPage> for HistoryPage {
        fn from(value: super::HistoryPage) -> Self {
            Self {
                entries: Ok(value.entries),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct HistoryQuery {
        before: ::std::result::Result<::std::option::Option<i64>, ::std::string::String>,
        limit: ::std::result::Result<::std::num::NonZeroU64, ::std::string::String>,
        query: ::std::result::Result<
            ::std::option::Option<super::HistoryQueryQuery>,
            ::std::string::String,
        >,
        type_: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for HistoryQuery {
        fn default() -> Self {
            Self {
                before: Ok(Default::default()),
                limit: Ok(super::defaults::default_nzu64::<::std::num::NonZeroU64, 20>()),
                query: Ok(Default::default()),
                type_: Ok(super::defaults::history_query_type()),
            }
        }
    }
    impl HistoryQuery {
        pub fn before<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::option::Option<i64>>,
            T::Error: ::std::fmt::Display,
        {
            self.before = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for before: {e}"));
            self
        }
        pub fn limit<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::num::NonZeroU64>,
            T::Error: ::std::fmt::Display,
        {
            self.limit = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for limit: {e}"));
            self
        }
        pub fn query<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::option::Option<super::HistoryQueryQuery>>,
            T::Error: ::std::fmt::Display,
        {
            self.query = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for query: {e}"));
            self
        }
        pub fn type_<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.type_ = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for type_: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<HistoryQuery> for super::HistoryQuery {
        type Error = super::error::ConversionError;
        fn try_from(
            value: HistoryQuery,
        ) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                before: value.before?,
                limit: value.limit?,
                query: value.query?,
                type_: value.type_?,
            })
        }
    }
    impl ::std::convert::From<super::HistoryQuery> for HistoryQuery {
        fn from(value: super::HistoryQuery) -> Self {
            Self {
                before: Ok(value.before),
                limit: Ok(value.limit),
                query: Ok(value.query),
                type_: Ok(value.type_),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct JournalEntry {
        arguments: ::std::result::Result<
            ::serde_json::Map<::std::string::String, ::serde_json::Value>,
            ::std::string::String,
        >,
        error_code: ::std::result::Result<
            ::std::option::Option<::std::string::String>,
            ::std::string::String,
        >,
        error_message: ::std::result::Result<
            ::std::option::Option<::std::string::String>,
            ::std::string::String,
        >,
        id: ::std::result::Result<i64, ::std::string::String>,
        ok: ::std::result::Result<bool, ::std::string::String>,
        recorded_at: ::std::result::Result<::std::string::String, ::std::string::String>,
        risk: ::std::result::Result<super::RiskLevel, ::std::string::String>,
        speech: ::std::result::Result<
            ::std::option::Option<::std::string::String>,
            ::std::string::String,
        >,
        tool: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for JournalEntry {
        fn default() -> Self {
            Self {
                arguments: Ok(Default::default()),
                error_code: Ok(Default::default()),
                error_message: Ok(Default::default()),
                id: Err("no value supplied for id".to_string()),
                ok: Err("no value supplied for ok".to_string()),
                recorded_at: Err("no value supplied for recorded_at".to_string()),
                risk: Err("no value supplied for risk".to_string()),
                speech: Ok(Default::default()),
                tool: Err("no value supplied for tool".to_string()),
            }
        }
    }
    impl JournalEntry {
        pub fn arguments<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<
                ::serde_json::Map<::std::string::String, ::serde_json::Value>,
            >,
            T::Error: ::std::fmt::Display,
        {
            self.arguments = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for arguments: {e}"));
            self
        }
        pub fn error_code<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::option::Option<::std::string::String>>,
            T::Error: ::std::fmt::Display,
        {
            self.error_code = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for error_code: {e}"));
            self
        }
        pub fn error_message<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::option::Option<::std::string::String>>,
            T::Error: ::std::fmt::Display,
        {
            self.error_message = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for error_message: {e}"));
            self
        }
        pub fn id<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<i64>,
            T::Error: ::std::fmt::Display,
        {
            self.id = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for id: {e}"));
            self
        }
        pub fn ok<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<bool>,
            T::Error: ::std::fmt::Display,
        {
            self.ok = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for ok: {e}"));
            self
        }
        pub fn recorded_at<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.recorded_at = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for recorded_at: {e}"));
            self
        }
        pub fn risk<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<super::RiskLevel>,
            T::Error: ::std::fmt::Display,
        {
            self.risk = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for risk: {e}"));
            self
        }
        pub fn speech<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::option::Option<::std::string::String>>,
            T::Error: ::std::fmt::Display,
        {
            self.speech = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for speech: {e}"));
            self
        }
        pub fn tool<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.tool = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for tool: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<JournalEntry> for super::JournalEntry {
        type Error = super::error::ConversionError;
        fn try_from(
            value: JournalEntry,
        ) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                arguments: value.arguments?,
                error_code: value.error_code?,
                error_message: value.error_message?,
                id: value.id?,
                ok: value.ok?,
                recorded_at: value.recorded_at?,
                risk: value.risk?,
                speech: value.speech?,
                tool: value.tool?,
            })
        }
    }
    impl ::std::convert::From<super::JournalEntry> for JournalEntry {
        fn from(value: super::JournalEntry) -> Self {
            Self {
                arguments: Ok(value.arguments),
                error_code: Ok(value.error_code),
                error_message: Ok(value.error_message),
                id: Ok(value.id),
                ok: Ok(value.ok),
                recorded_at: Ok(value.recorded_at),
                risk: Ok(value.risk),
                speech: Ok(value.speech),
                tool: Ok(value.tool),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct PermissionChanged {
        permission: ::std::result::Result<super::Permission, ::std::string::String>,
        state: ::std::result::Result<super::PermissionState, ::std::string::String>,
        type_: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for PermissionChanged {
        fn default() -> Self {
            Self {
                permission: Err("no value supplied for permission".to_string()),
                state: Err("no value supplied for state".to_string()),
                type_: Ok(super::defaults::permission_changed_type()),
            }
        }
    }
    impl PermissionChanged {
        pub fn permission<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<super::Permission>,
            T::Error: ::std::fmt::Display,
        {
            self.permission = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for permission: {e}"));
            self
        }
        pub fn state<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<super::PermissionState>,
            T::Error: ::std::fmt::Display,
        {
            self.state = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for state: {e}"));
            self
        }
        pub fn type_<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.type_ = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for type_: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<PermissionChanged> for super::PermissionChanged {
        type Error = super::error::ConversionError;
        fn try_from(
            value: PermissionChanged,
        ) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                permission: value.permission?,
                state: value.state?,
                type_: value.type_?,
            })
        }
    }
    impl ::std::convert::From<super::PermissionChanged> for PermissionChanged {
        fn from(value: super::PermissionChanged) -> Self {
            Self {
                permission: Ok(value.permission),
                state: Ok(value.state),
                type_: Ok(value.type_),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct PermissionReport {
        permission: ::std::result::Result<super::Permission, ::std::string::String>,
        state: ::std::result::Result<super::PermissionState, ::std::string::String>,
        type_: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for PermissionReport {
        fn default() -> Self {
            Self {
                permission: Err("no value supplied for permission".to_string()),
                state: Err("no value supplied for state".to_string()),
                type_: Ok(super::defaults::permission_report_type()),
            }
        }
    }
    impl PermissionReport {
        pub fn permission<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<super::Permission>,
            T::Error: ::std::fmt::Display,
        {
            self.permission = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for permission: {e}"));
            self
        }
        pub fn state<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<super::PermissionState>,
            T::Error: ::std::fmt::Display,
        {
            self.state = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for state: {e}"));
            self
        }
        pub fn type_<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.type_ = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for type_: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<PermissionReport> for super::PermissionReport {
        type Error = super::error::ConversionError;
        fn try_from(
            value: PermissionReport,
        ) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                permission: value.permission?,
                state: value.state?,
                type_: value.type_?,
            })
        }
    }
    impl ::std::convert::From<super::PermissionReport> for PermissionReport {
        fn from(value: super::PermissionReport) -> Self {
            Self {
                permission: Ok(value.permission),
                state: Ok(value.state),
                type_: Ok(value.type_),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct Request {
        command: ::std::result::Result<super::Command, ::std::string::String>,
        id: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for Request {
        fn default() -> Self {
            Self {
                command: Err("no value supplied for command".to_string()),
                id: Err("no value supplied for id".to_string()),
            }
        }
    }
    impl Request {
        pub fn command<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<super::Command>,
            T::Error: ::std::fmt::Display,
        {
            self.command = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for command: {e}"));
            self
        }
        pub fn id<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.id = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for id: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<Request> for super::Request {
        type Error = super::error::ConversionError;
        fn try_from(value: Request) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                command: value.command?,
                id: value.id?,
            })
        }
    }
    impl ::std::convert::From<super::Request> for Request {
        fn from(value: super::Request) -> Self {
            Self {
                command: Ok(value.command),
                id: Ok(value.id),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct Response {
        error: ::std::result::Result<
            ::std::option::Option<super::ResponseError>,
            ::std::string::String,
        >,
        id: ::std::result::Result<::std::string::String, ::std::string::String>,
        ok: ::std::result::Result<bool, ::std::string::String>,
        payload: ::std::result::Result<
            ::serde_json::Map<::std::string::String, ::serde_json::Value>,
            ::std::string::String,
        >,
    }
    impl ::std::default::Default for Response {
        fn default() -> Self {
            Self {
                error: Ok(Default::default()),
                id: Err("no value supplied for id".to_string()),
                ok: Err("no value supplied for ok".to_string()),
                payload: Ok(Default::default()),
            }
        }
    }
    impl Response {
        pub fn error<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::option::Option<super::ResponseError>>,
            T::Error: ::std::fmt::Display,
        {
            self.error = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for error: {e}"));
            self
        }
        pub fn id<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.id = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for id: {e}"));
            self
        }
        pub fn ok<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<bool>,
            T::Error: ::std::fmt::Display,
        {
            self.ok = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for ok: {e}"));
            self
        }
        pub fn payload<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<
                ::serde_json::Map<::std::string::String, ::serde_json::Value>,
            >,
            T::Error: ::std::fmt::Display,
        {
            self.payload = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for payload: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<Response> for super::Response {
        type Error = super::error::ConversionError;
        fn try_from(value: Response) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                error: value.error?,
                id: value.id?,
                ok: value.ok?,
                payload: value.payload?,
            })
        }
    }
    impl ::std::convert::From<super::Response> for Response {
        fn from(value: super::Response) -> Self {
            Self {
                error: Ok(value.error),
                id: Ok(value.id),
                ok: Ok(value.ok),
                payload: Ok(value.payload),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct ResponseError {
        code: ::std::result::Result<::std::string::String, ::std::string::String>,
        message: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for ResponseError {
        fn default() -> Self {
            Self {
                code: Err("no value supplied for code".to_string()),
                message: Err("no value supplied for message".to_string()),
            }
        }
    }
    impl ResponseError {
        pub fn code<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.code = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for code: {e}"));
            self
        }
        pub fn message<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.message = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for message: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<ResponseError> for super::ResponseError {
        type Error = super::error::ConversionError;
        fn try_from(
            value: ResponseError,
        ) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                code: value.code?,
                message: value.message?,
            })
        }
    }
    impl ::std::convert::From<super::ResponseError> for ResponseError {
        fn from(value: super::ResponseError) -> Self {
            Self {
                code: Ok(value.code),
                message: Ok(value.message),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct SessionCancel {
        type_: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for SessionCancel {
        fn default() -> Self {
            Self {
                type_: Ok(super::defaults::session_cancel_type()),
            }
        }
    }
    impl SessionCancel {
        pub fn type_<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.type_ = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for type_: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<SessionCancel> for super::SessionCancel {
        type Error = super::error::ConversionError;
        fn try_from(
            value: SessionCancel,
        ) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                type_: value.type_?,
            })
        }
    }
    impl ::std::convert::From<super::SessionCancel> for SessionCancel {
        fn from(value: super::SessionCancel) -> Self {
            Self {
                type_: Ok(value.type_),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct SpeechRequested {
        interrupt: ::std::result::Result<bool, ::std::string::String>,
        text: ::std::result::Result<::std::string::String, ::std::string::String>,
        type_: ::std::result::Result<::std::string::String, ::std::string::String>,
        voice: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for SpeechRequested {
        fn default() -> Self {
            Self {
                interrupt: Ok(Default::default()),
                text: Err("no value supplied for text".to_string()),
                type_: Ok(super::defaults::speech_requested_type()),
                voice: Err("no value supplied for voice".to_string()),
            }
        }
    }
    impl SpeechRequested {
        pub fn interrupt<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<bool>,
            T::Error: ::std::fmt::Display,
        {
            self.interrupt = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for interrupt: {e}"));
            self
        }
        pub fn text<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.text = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for text: {e}"));
            self
        }
        pub fn type_<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.type_ = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for type_: {e}"));
            self
        }
        pub fn voice<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.voice = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for voice: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<SpeechRequested> for super::SpeechRequested {
        type Error = super::error::ConversionError;
        fn try_from(
            value: SpeechRequested,
        ) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                interrupt: value.interrupt?,
                text: value.text?,
                type_: value.type_?,
                voice: value.voice?,
            })
        }
    }
    impl ::std::convert::From<super::SpeechRequested> for SpeechRequested {
        fn from(value: super::SpeechRequested) -> Self {
            Self {
                interrupt: Ok(value.interrupt),
                text: Ok(value.text),
                type_: Ok(value.type_),
                voice: Ok(value.voice),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct StateChanged {
        state: ::std::result::Result<super::State, ::std::string::String>,
        type_: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for StateChanged {
        fn default() -> Self {
            Self {
                state: Err("no value supplied for state".to_string()),
                type_: Ok(super::defaults::state_changed_type()),
            }
        }
    }
    impl StateChanged {
        pub fn state<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<super::State>,
            T::Error: ::std::fmt::Display,
        {
            self.state = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for state: {e}"));
            self
        }
        pub fn type_<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.type_ = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for type_: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<StateChanged> for super::StateChanged {
        type Error = super::error::ConversionError;
        fn try_from(
            value: StateChanged,
        ) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                state: value.state?,
                type_: value.type_?,
            })
        }
    }
    impl ::std::convert::From<super::StateChanged> for StateChanged {
        fn from(value: super::StateChanged) -> Self {
            Self {
                state: Ok(value.state),
                type_: Ok(value.type_),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct ToolCompleted {
        error: ::std::result::Result<
            ::std::option::Option<::std::string::String>,
            ::std::string::String,
        >,
        ok: ::std::result::Result<bool, ::std::string::String>,
        speech: ::std::result::Result<
            ::std::option::Option<::std::string::String>,
            ::std::string::String,
        >,
        tool: ::std::result::Result<::std::string::String, ::std::string::String>,
        type_: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for ToolCompleted {
        fn default() -> Self {
            Self {
                error: Ok(Default::default()),
                ok: Err("no value supplied for ok".to_string()),
                speech: Ok(Default::default()),
                tool: Err("no value supplied for tool".to_string()),
                type_: Ok(super::defaults::tool_completed_type()),
            }
        }
    }
    impl ToolCompleted {
        pub fn error<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::option::Option<::std::string::String>>,
            T::Error: ::std::fmt::Display,
        {
            self.error = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for error: {e}"));
            self
        }
        pub fn ok<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<bool>,
            T::Error: ::std::fmt::Display,
        {
            self.ok = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for ok: {e}"));
            self
        }
        pub fn speech<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::option::Option<::std::string::String>>,
            T::Error: ::std::fmt::Display,
        {
            self.speech = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for speech: {e}"));
            self
        }
        pub fn tool<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.tool = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for tool: {e}"));
            self
        }
        pub fn type_<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.type_ = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for type_: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<ToolCompleted> for super::ToolCompleted {
        type Error = super::error::ConversionError;
        fn try_from(
            value: ToolCompleted,
        ) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                error: value.error?,
                ok: value.ok?,
                speech: value.speech?,
                tool: value.tool?,
                type_: value.type_?,
            })
        }
    }
    impl ::std::convert::From<super::ToolCompleted> for ToolCompleted {
        fn from(value: super::ToolCompleted) -> Self {
            Self {
                error: Ok(value.error),
                ok: Ok(value.ok),
                speech: Ok(value.speech),
                tool: Ok(value.tool),
                type_: Ok(value.type_),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct TranscriptionPartial {
        text: ::std::result::Result<::std::string::String, ::std::string::String>,
        type_: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for TranscriptionPartial {
        fn default() -> Self {
            Self {
                text: Err("no value supplied for text".to_string()),
                type_: Ok(super::defaults::transcription_partial_type()),
            }
        }
    }
    impl TranscriptionPartial {
        pub fn text<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.text = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for text: {e}"));
            self
        }
        pub fn type_<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.type_ = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for type_: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<TranscriptionPartial> for super::TranscriptionPartial {
        type Error = super::error::ConversionError;
        fn try_from(
            value: TranscriptionPartial,
        ) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                text: value.text?,
                type_: value.type_?,
            })
        }
    }
    impl ::std::convert::From<super::TranscriptionPartial> for TranscriptionPartial {
        fn from(value: super::TranscriptionPartial) -> Self {
            Self {
                text: Ok(value.text),
                type_: Ok(value.type_),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct UtteranceSubmit {
        locale: ::std::result::Result<
            ::std::option::Option<::std::string::String>,
            ::std::string::String,
        >,
        text: ::std::result::Result<super::Text, ::std::string::String>,
        type_: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for UtteranceSubmit {
        fn default() -> Self {
            Self {
                locale: Ok(Default::default()),
                text: Err("no value supplied for text".to_string()),
                type_: Ok(super::defaults::utterance_submit_type()),
            }
        }
    }
    impl UtteranceSubmit {
        pub fn locale<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::option::Option<::std::string::String>>,
            T::Error: ::std::fmt::Display,
        {
            self.locale = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for locale: {e}"));
            self
        }
        pub fn text<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<super::Text>,
            T::Error: ::std::fmt::Display,
        {
            self.text = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for text: {e}"));
            self
        }
        pub fn type_<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.type_ = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for type_: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<UtteranceSubmit> for super::UtteranceSubmit {
        type Error = super::error::ConversionError;
        fn try_from(
            value: UtteranceSubmit,
        ) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                locale: value.locale?,
                text: value.text?,
                type_: value.type_?,
            })
        }
    }
    impl ::std::convert::From<super::UtteranceSubmit> for UtteranceSubmit {
        fn from(value: super::UtteranceSubmit) -> Self {
            Self {
                locale: Ok(value.locale),
                text: Ok(value.text),
                type_: Ok(value.type_),
            }
        }
    }
    #[derive(Clone, Debug)]
    pub struct VisionSubmit {
        image: ::std::result::Result<super::Image, ::std::string::String>,
        locale: ::std::result::Result<
            ::std::option::Option<::std::string::String>,
            ::std::string::String,
        >,
        text: ::std::result::Result<
            ::std::option::Option<super::VisionSubmitText>,
            ::std::string::String,
        >,
        type_: ::std::result::Result<::std::string::String, ::std::string::String>,
    }
    impl ::std::default::Default for VisionSubmit {
        fn default() -> Self {
            Self {
                image: Err("no value supplied for image".to_string()),
                locale: Ok(Default::default()),
                text: Ok(Default::default()),
                type_: Ok(super::defaults::vision_submit_type()),
            }
        }
    }
    impl VisionSubmit {
        pub fn image<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<super::Image>,
            T::Error: ::std::fmt::Display,
        {
            self.image = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for image: {e}"));
            self
        }
        pub fn locale<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::option::Option<::std::string::String>>,
            T::Error: ::std::fmt::Display,
        {
            self.locale = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for locale: {e}"));
            self
        }
        pub fn text<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::option::Option<super::VisionSubmitText>>,
            T::Error: ::std::fmt::Display,
        {
            self.text = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for text: {e}"));
            self
        }
        pub fn type_<T>(mut self, value: T) -> Self
        where
            T: ::std::convert::TryInto<::std::string::String>,
            T::Error: ::std::fmt::Display,
        {
            self.type_ = value
                .try_into()
                .map_err(|e| format!("error converting supplied value for type_: {e}"));
            self
        }
    }
    impl ::std::convert::TryFrom<VisionSubmit> for super::VisionSubmit {
        type Error = super::error::ConversionError;
        fn try_from(
            value: VisionSubmit,
        ) -> ::std::result::Result<Self, super::error::ConversionError> {
            Ok(Self {
                image: value.image?,
                locale: value.locale?,
                text: value.text?,
                type_: value.type_?,
            })
        }
    }
    impl ::std::convert::From<super::VisionSubmit> for VisionSubmit {
        fn from(value: super::VisionSubmit) -> Self {
            Self {
                image: Ok(value.image),
                locale: Ok(value.locale),
                text: Ok(value.text),
                type_: Ok(value.type_),
            }
        }
    }
}
#[doc = r" Generation of default values for serde."]
pub mod defaults {
    pub(super) fn default_u64<T, const V: u64>() -> T
    where
        T: ::std::convert::TryFrom<u64>,
        <T as ::std::convert::TryFrom<u64>>::Error: ::std::fmt::Debug,
    {
        T::try_from(V).unwrap()
    }
    pub(super) fn default_nzu64<T, const V: u64>() -> T
    where
        T: ::std::convert::TryFrom<::std::num::NonZeroU64>,
        <T as ::std::convert::TryFrom<::std::num::NonZeroU64>>::Error: ::std::fmt::Debug,
    {
        T::try_from(::std::num::NonZeroU64::try_from(V).unwrap()).unwrap()
    }
    pub(super) fn audio_submit_type() -> ::std::string::String {
        "audio.submit".to_string()
    }
    pub(super) fn confirmation_required_type() -> ::std::string::String {
        "confirmation.required".to_string()
    }
    pub(super) fn confirmation_respond_type() -> ::std::string::String {
        "confirmation.respond".to_string()
    }
    pub(super) fn hello_type() -> ::std::string::String {
        "hello".to_string()
    }
    pub(super) fn history_query_type() -> ::std::string::String {
        "history.query".to_string()
    }
    pub(super) fn permission_changed_type() -> ::std::string::String {
        "permission.changed".to_string()
    }
    pub(super) fn permission_report_type() -> ::std::string::String {
        "permission.report".to_string()
    }
    pub(super) fn session_cancel_type() -> ::std::string::String {
        "session.cancel".to_string()
    }
    pub(super) fn speech_requested_type() -> ::std::string::String {
        "speech.requested".to_string()
    }
    pub(super) fn state_changed_type() -> ::std::string::String {
        "state.changed".to_string()
    }
    pub(super) fn tool_completed_type() -> ::std::string::String {
        "tool.completed".to_string()
    }
    pub(super) fn transcription_partial_type() -> ::std::string::String {
        "transcription.partial".to_string()
    }
    pub(super) fn utterance_submit_type() -> ::std::string::String {
        "utterance.submit".to_string()
    }
    pub(super) fn vision_submit_type() -> ::std::string::String {
        "vision.submit".to_string()
    }
}
