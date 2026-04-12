import { useEffect, useRef, useState, useCallback } from "react";
import {
  Room,
  RoomEvent,
  type RemoteParticipant,
} from "livekit-client";
import { getLiveKitToken } from "@/api/meetings";

export type LkStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected"
  | "error";

export interface LkState {
  room: Room | null;
  status: LkStatus;
  error: Error | null;
  participants: RemoteParticipant[];
  activeSpeakerIdentities: string[];
  localMicEnabled: boolean;
  enableMic: (enabled: boolean) => Promise<void>;
  enableCamera: (enabled: boolean) => Promise<void>;
}

export function useLiveKitRoom(meetingId: string | null): LkState {
  const [status, setStatus] = useState<LkStatus>("idle");
  const [error, setError] = useState<Error | null>(null);
  const [participants, setParticipants] = useState<RemoteParticipant[]>([]);
  const [activeSpeakerIdentities, setActiveSpeakerIdentities] = useState<
    string[]
  >([]);
  const [localMicEnabled, setLocalMicEnabled] = useState(false);

  // Stable room ref — avoids re-renders triggering reconnect
  const roomRef = useRef<Room | null>(null);
  // StrictMode double-mount guard
  const mountedRef = useRef(false);

  const enableMic = useCallback(async (enabled: boolean) => {
    const room = roomRef.current;
    if (!room) return;
    await room.localParticipant.setMicrophoneEnabled(enabled);
    setLocalMicEnabled(enabled);
  }, []);

  const enableCamera = useCallback(async (enabled: boolean) => {
    const room = roomRef.current;
    if (!room) return;
    await room.localParticipant.setCameraEnabled(enabled);
  }, []);

  useEffect(() => {
    if (!meetingId) return;

    // React 19 StrictMode fires effects twice in development.
    // Skip the second mount so we don't create a duplicate Room.
    if (mountedRef.current) return;
    mountedRef.current = true;

    let cancelled = false;

    const room = new Room({ adaptiveStream: true, dynacast: true });
    roomRef.current = room;

    function syncParticipants() {
      setParticipants(Array.from(room.remoteParticipants.values()));
    }

    room
      .on(RoomEvent.ParticipantConnected, syncParticipants)
      .on(RoomEvent.ParticipantDisconnected, syncParticipants)
      .on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        setActiveSpeakerIdentities(speakers.map((s) => s.identity));
      })
      .on(RoomEvent.Disconnected, () => {
        if (!cancelled) setStatus("disconnected");
      })
      .on(RoomEvent.Reconnecting, () => {
        if (!cancelled) setStatus("reconnecting");
      })
      .on(RoomEvent.Reconnected, () => {
        if (!cancelled) setStatus("connected");
      });

    // Expose debug handles in non-production environments
    if (import.meta.env.MODE !== "production") {
      (window as unknown as Record<string, unknown>).__lkRoom = room;
      (window as unknown as Record<string, unknown>).__lkStatus = () => status;
      (window as unknown as Record<string, unknown>).__lkParticipants = () =>
        Array.from(room.remoteParticipants.values());
    }

    async function connect() {
      setStatus("connecting");
      setError(null);
      try {
        const { token, url } = await getLiveKitToken(meetingId as string);
        if (cancelled) return;
        await room.connect(url, token);
        if (cancelled) {
          await room.disconnect();
          return;
        }
        await room.localParticipant.setMicrophoneEnabled(true);
        setLocalMicEnabled(true);
        syncParticipants();
        setStatus("connected");
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)));
          setStatus("error");
        }
      }
    }

    void connect();

    return () => {
      cancelled = true;
      mountedRef.current = false;
      roomRef.current = null;
      void room.disconnect();
      if (import.meta.env.MODE !== "production") {
        delete (window as unknown as Record<string, unknown>).__lkRoom;
        delete (window as unknown as Record<string, unknown>).__lkStatus;
        delete (window as unknown as Record<string, unknown>).__lkParticipants;
      }
    };
  }, [meetingId]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    room: roomRef.current,
    status,
    error,
    participants,
    activeSpeakerIdentities,
    localMicEnabled,
    enableMic,
    enableCamera,
  };
}
