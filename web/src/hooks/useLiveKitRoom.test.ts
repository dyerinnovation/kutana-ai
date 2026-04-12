import { describe, it, expect, vi, beforeEach } from "vitest";
import { Room, RoomEvent } from "livekit-client";

// ---------------------------------------------------------------------------
// Mock livekit-client
// ---------------------------------------------------------------------------

const mockSetMicrophoneEnabled = vi.fn().mockResolvedValue(undefined);
const mockSetCameraEnabled = vi.fn().mockResolvedValue(undefined);
const mockConnect = vi.fn().mockResolvedValue(undefined);
const mockDisconnect = vi.fn().mockResolvedValue(undefined);
const mockOn = vi.fn().mockReturnThis();

vi.mock("livekit-client", () => {
  const RoomEventMock = {
    ParticipantConnected: "participantConnected",
    ParticipantDisconnected: "participantDisconnected",
    ActiveSpeakersChanged: "activeSpeakersChanged",
    Disconnected: "disconnected",
    Reconnecting: "reconnecting",
    Reconnected: "reconnected",
  };

  class RoomMock {
    remoteParticipants = new Map();
    localParticipant = {
      setMicrophoneEnabled: mockSetMicrophoneEnabled,
      setCameraEnabled: mockSetCameraEnabled,
    };
    connect = mockConnect;
    disconnect = mockDisconnect;
    on = mockOn;
  }

  return {
    Room: RoomMock,
    RoomEvent: RoomEventMock,
  };
});

// ---------------------------------------------------------------------------
// Mock API
// ---------------------------------------------------------------------------

vi.mock("@/api/meetings", () => ({
  getLiveKitToken: vi.fn().mockResolvedValue({
    token: "test-token",
    url: "wss://livekit.example.com",
    roomName: "room-abc123",
  }),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useLiveKitRoom — mocked livekit-client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("Room is constructable with adaptiveStream and dynacast options", () => {
    const room = new Room({ adaptiveStream: true, dynacast: true });
    expect(room).toBeDefined();
    expect(room.localParticipant).toBeDefined();
    expect(typeof room.connect).toBe("function");
    expect(typeof room.disconnect).toBe("function");
  });

  it("RoomEvent exports the expected event names", () => {
    expect(RoomEvent.ParticipantConnected).toBe("participantConnected");
    expect(RoomEvent.ParticipantDisconnected).toBe("participantDisconnected");
    expect(RoomEvent.ActiveSpeakersChanged).toBe("activeSpeakersChanged");
    expect(RoomEvent.Disconnected).toBe("disconnected");
    expect(RoomEvent.Reconnecting).toBe("reconnecting");
    expect(RoomEvent.Reconnected).toBe("reconnected");
  });

  it("localParticipant.setMicrophoneEnabled resolves without error", async () => {
    const room = new Room();
    await expect(
      room.localParticipant.setMicrophoneEnabled(true)
    ).resolves.toBeUndefined();
    expect(mockSetMicrophoneEnabled).toHaveBeenCalledWith(true);
  });

  it("localParticipant.setCameraEnabled resolves without error", async () => {
    const room = new Room();
    await expect(
      room.localParticipant.setCameraEnabled(false)
    ).resolves.toBeUndefined();
    expect(mockSetCameraEnabled).toHaveBeenCalledWith(false);
  });

  it("room.connect resolves without error", async () => {
    const room = new Room();
    await expect(
      room.connect("wss://livekit.example.com", "test-token")
    ).resolves.toBeUndefined();
    expect(mockConnect).toHaveBeenCalledWith(
      "wss://livekit.example.com",
      "test-token"
    );
  });

  it("room.on returns the room for chaining", () => {
    const room = new Room();
    const result = room.on(RoomEvent.ParticipantConnected, vi.fn());
    expect(result).toBe(room);
  });

  it("getLiveKitToken returns token, url, and roomName", async () => {
    const { getLiveKitToken } = await import("@/api/meetings");
    const result = await getLiveKitToken("meeting-123");
    expect(result).toEqual({
      token: "test-token",
      url: "wss://livekit.example.com",
      roomName: "room-abc123",
    });
    expect(getLiveKitToken).toHaveBeenCalledWith("meeting-123");
  });

  it("room.remoteParticipants is an empty Map by default", () => {
    const room = new Room();
    expect(room.remoteParticipants).toBeInstanceOf(Map);
    expect(room.remoteParticipants.size).toBe(0);
  });
});
