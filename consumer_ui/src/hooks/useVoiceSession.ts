import { useCallback, useEffect, useRef, useState } from 'react';

import { getVoiceApiBaseUrl } from '../api';
import {
  parseServerUiEvent,
  type ClientUiEvent,
  type ConnectionStatus,
  type ServerUiEvent,
} from '../types';

interface UseVoiceSessionOptions {
  tenantId: string;
  persona?: string;
  onServerEvent: (event: ServerUiEvent) => void;
}

interface VoiceOfferResponse {
  sdp: string;
  type: 'answer';
  pc_id: string;
}

interface IceCandidatePayload {
  candidate: string;
  sdp_mid: string;
  sdp_mline_index: number;
}

export interface VoiceSessionController {
  status: ConnectionStatus;
  errorMessage: string | null;
  microphoneStream: MediaStream | null;
  remoteAudioRef: React.RefObject<HTMLAudioElement | null>;
  connect: () => Promise<void>;
  disconnect: () => void;
  sendEvent: (event: ClientUiEvent) => boolean;
  setPushToTalk: (active: boolean) => void;
}

/**
 * Owns a browser WebRTC connection, microphone lifecycle, and typed UI bus.
 * The hook never permits a direct browser-side booking or payment command.
 */
export function useVoiceSession({ tenantId, persona, onServerEvent }: UseVoiceSessionOptions): VoiceSessionController {
  const [status, setStatus] = useState<ConnectionStatus>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [microphoneStream, setMicrophoneStream] = useState<MediaStream | null>(null);
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const dataChannelRef = useRef<RTCDataChannel | null>(null);
  const microphoneStreamRef = useRef<MediaStream | null>(null);
  const pcIdRef = useRef<string | null>(null);
  const pendingCandidatesRef = useRef<IceCandidatePayload[]>([]);
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null);
  const onServerEventRef = useRef(onServerEvent);
  onServerEventRef.current = onServerEvent;

  const disconnect = useCallback(() => {
    dataChannelRef.current?.close();
    dataChannelRef.current = null;
    peerConnectionRef.current?.close();
    peerConnectionRef.current = null;
    microphoneStreamRef.current?.getTracks().forEach((track) => track.stop());
    microphoneStreamRef.current = null;
    pendingCandidatesRef.current = [];
    pcIdRef.current = null;
    if (remoteAudioRef.current) remoteAudioRef.current.srcObject = null;
    setMicrophoneStream(null);
    setStatus('ended');
  }, []);

  const sendCandidates = useCallback(async (candidates: IceCandidatePayload[]) => {
    const pcId = pcIdRef.current;
    if (!pcId || candidates.length === 0) return;
    try {
      const response = await fetch(`${getVoiceApiBaseUrl()}/api/v1/voice/offer`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pc_id: pcId, candidates }),
      });
      if (!response.ok) throw new Error('Unable to exchange network candidates.');
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to exchange network candidates.');
    }
  }, []);

  const connect = useCallback(async () => {
    if (peerConnectionRef.current) return;
    setErrorMessage(null);
    setStatus('requesting-permission');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
        video: false,
      });
      microphoneStreamRef.current = stream;
      setMicrophoneStream(stream);
      stream.getAudioTracks().forEach((track) => {
        track.enabled = false;
      });

      const peerConnection = new RTCPeerConnection();
      peerConnectionRef.current = peerConnection;
      stream.getTracks().forEach((track) => peerConnection.addTrack(track, stream));
      const dataChannel = peerConnection.createDataChannel('omnivox-ui-bus', { ordered: true });
      dataChannelRef.current = dataChannel;

      dataChannel.onopen = () => setStatus('connected');
      dataChannel.onclose = () => {
        if (peerConnection.connectionState === 'connected') setStatus('visual-unavailable');
      };
      dataChannel.onerror = () => setErrorMessage('The visual conversation channel encountered a problem.');
      dataChannel.onmessage = (messageEvent) => {
        const raw = safelyParseJson(messageEvent.data);
        const event = parseServerUiEvent(raw);
        if (event) onServerEventRef.current(event);
      };
      peerConnection.ontrack = (event) => {
        if (remoteAudioRef.current) remoteAudioRef.current.srcObject = event.streams[0] ?? new MediaStream([event.track]);
      };
      peerConnection.onconnectionstatechange = () => {
        if (peerConnection.connectionState === 'failed') {
          setStatus('error');
          setErrorMessage('The voice connection failed. Please reconnect.');
        }
        if (peerConnection.connectionState === 'disconnected') setStatus('visual-unavailable');
      };
      peerConnection.onicecandidate = (event) => {
        const candidate = serializeCandidate(event.candidate);
        if (!candidate) return;
        if (!pcIdRef.current) {
          pendingCandidatesRef.current.push(candidate);
          return;
        }
        void sendCandidates([candidate]);
      };

      setStatus('connecting');
      const offer = await peerConnection.createOffer();
      await peerConnection.setLocalDescription(offer);
      const response = await postOffer({
        sdp: offer.sdp ?? null,
        type: offer.type,
        request_data: { tenant_id: tenantId, ...(persona ? { persona } : {}) },
      });
      pcIdRef.current = response.pc_id;
      await peerConnection.setRemoteDescription({ type: response.type, sdp: response.sdp });
      const queuedCandidates = pendingCandidatesRef.current.splice(0);
      await sendCandidates(queuedCandidates);
    } catch (error) {
      peerConnectionRef.current?.close();
      peerConnectionRef.current = null;
      microphoneStreamRef.current?.getTracks().forEach((track) => track.stop());
      microphoneStreamRef.current = null;
      setMicrophoneStream(null);
      setStatus('error');
      setErrorMessage(toConnectionMessage(error));
    }
  }, [persona, sendCandidates, tenantId]);

  const sendEvent = useCallback((event: ClientUiEvent): boolean => {
    const channel = dataChannelRef.current;
    if (!channel || channel.readyState !== 'open') {
      setErrorMessage('Connect to Elena before sending a screen action.');
      return false;
    }
    channel.send(JSON.stringify(event));
    return true;
  }, []);

  const setPushToTalk = useCallback((active: boolean) => {
    microphoneStreamRef.current?.getAudioTracks().forEach((track) => {
      track.enabled = active;
    });
    sendEvent({ type: 'ptt_state', active });
  }, [sendEvent]);

  useEffect(() => disconnect, [disconnect]);

  return { status, errorMessage, microphoneStream, remoteAudioRef, connect, disconnect, sendEvent, setPushToTalk };
}

async function postOffer(payload: {
  sdp: string | null;
  type: RTCSdpType;
  request_data: { tenant_id: string; persona?: string };
}): Promise<VoiceOfferResponse> {
  if (!payload.sdp || payload.type !== 'offer') throw new Error('The browser could not prepare a voice offer.');
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15_000);
  try {
    const response = await fetch(`${getVoiceApiBaseUrl()}/api/v1/voice/offer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error('The concierge could not establish a secure voice session.');
    return (await response.json()) as VoiceOfferResponse;
  } finally {
    window.clearTimeout(timeout);
  }
}

function serializeCandidate(candidate: RTCIceCandidate | null): IceCandidatePayload | null {
  if (!candidate || !candidate.candidate || candidate.sdpMid === null || candidate.sdpMLineIndex === null) return null;
  return {
    candidate: candidate.candidate,
    sdp_mid: candidate.sdpMid,
    sdp_mline_index: candidate.sdpMLineIndex,
  };
}

function safelyParseJson(value: unknown): unknown {
  if (typeof value !== 'string') return null;
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return null;
  }
}

function toConnectionMessage(error: unknown): string {
  if (error instanceof DOMException && error.name === 'NotAllowedError') {
    return 'Microphone access is required to start a private voice conversation.';
  }
  if (error instanceof Error && error.name === 'AbortError') {
    return 'The secure voice connection timed out. Please try again.';
  }
  return error instanceof Error ? error.message : 'Unable to start the voice connection.';
}
