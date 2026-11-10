// What the Mac is playing, whatever the output device, as a Core Audio process tap (macOS
// 14.2+): raw float32 frames to stdout, one line "rate R channels C" to stderr first. Built by
// beat/install.sh into beat/.venv/bin/systap; beat_osc.py runs it for Beatsource "system".
// The first run asks for system audio recording permission, attributed to the terminal app
// it runs from; a refusal is not an error, the tap then delivers silence.
import AudioToolbox
import CoreAudio
import Foundation

func check(_ err: OSStatus, _ what: String) {
    if err != noErr { FileHandle.standardError.write("\(what): \(err)\n".data(using: .utf8)!); exit(1) }
}

let out = FileHandle.standardOutput
var addr = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDefaultOutputDevice,
                                      mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
var dev = AudioObjectID(kAudioObjectUnknown)
var size = UInt32(MemoryLayout<AudioObjectID>.size)
check(AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size, &dev), "default output")
addr.mSelector = kAudioDevicePropertyDeviceUID
var uid: CFString = "" as CFString
size = UInt32(MemoryLayout<CFString>.size)
check(AudioObjectGetPropertyData(dev, &addr, 0, nil, &size, &uid), "output uid")

let tapDesc = CATapDescription(stereoGlobalTapButExcludeProcesses: [])
tapDesc.name = "beat tap"
tapDesc.isPrivate = true
tapDesc.muteBehavior = .unmuted
var tap = AudioObjectID(kAudioObjectUnknown)
check(AudioHardwareCreateProcessTap(tapDesc, &tap), "create tap")

let agg: [String: Any] = [
    kAudioAggregateDeviceNameKey: "beat tap aggregate",
    kAudioAggregateDeviceUIDKey: UUID().uuidString,
    kAudioAggregateDeviceMainSubDeviceKey: uid,
    kAudioAggregateDeviceIsPrivateKey: true,
    kAudioAggregateDeviceTapAutoStartKey: true,
    kAudioAggregateDeviceSubDeviceListKey: [[kAudioSubDeviceUIDKey: uid]],
    kAudioAggregateDeviceTapListKey: [[kAudioSubTapDriftCompensationKey: true, kAudioSubTapUIDKey: tapDesc.uuid.uuidString]],
]
var aggID = AudioObjectID(kAudioObjectUnknown)
check(AudioHardwareCreateAggregateDevice(agg as CFDictionary, &aggID), "aggregate")

var fmt = AudioStreamBasicDescription()
size = UInt32(MemoryLayout<AudioStreamBasicDescription>.size)
addr = AudioObjectPropertyAddress(mSelector: kAudioTapPropertyFormat, mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
check(AudioObjectGetPropertyData(tap, &addr, 0, nil, &size, &fmt), "tap format")
if fmt.mFormatFlags & kAudioFormatFlagIsNonInterleaved != 0 || fmt.mBitsPerChannel != 32 {
    FileHandle.standardError.write("unexpected tap format\n".data(using: .utf8)!); exit(1)
}
// the rate the frames actually arrive at is the aggregate's, not the tap format's: with
// Bluetooth headphones the format said 48000 and 44100 arrived (2026-11-10)
var rate = Float64(0)
size = UInt32(MemoryLayout<Float64>.size)
addr = AudioObjectPropertyAddress(mSelector: kAudioDevicePropertyNominalSampleRate, mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
check(AudioObjectGetPropertyData(aggID, &addr, 0, nil, &size, &rate), "aggregate rate")
FileHandle.standardError.write("rate \(Int(rate)) channels \(fmt.mChannelsPerFrame)\n".data(using: .utf8)!)

var proc: AudioDeviceIOProcID?
check(AudioDeviceCreateIOProcIDWithBlock(&proc, aggID, nil) { _, inData, _, _, _ in
    let list = UnsafeMutableAudioBufferListPointer(UnsafeMutablePointer(mutating: inData))
    for buf in list where buf.mData != nil {
        out.write(Data(bytes: buf.mData!, count: Int(buf.mDataByteSize)))
    }
}, "io proc")
check(AudioDeviceStart(aggID, proc), "start")
signal(SIGTERM) { _ in exit(0) }
signal(SIGPIPE) { _ in exit(0) }
while true { Thread.sleep(forTimeInterval: 1) }
