/** Shared browser contracts that mirror the bounded consumer voice API. */

export type ConnectionStatus =
  | 'idle'
  | 'requesting-permission'
  | 'connecting'
  | 'connected'
  | 'visual-unavailable'
  | 'error'
  | 'ended';

export interface ConsumerConfiguration {
  tenant_id: string;
  tenant_name: string;
  agent_name: string;
  persona: string;
  voice_transport: 'smallwebrtc';
  confirmation_required: boolean;
  payment_collection_available: boolean;
}

export interface RoomCardModel {
  id: string;
  name: string;
  description: string;
  price_per_night: number;
  currency: string;
  image_url?: string;
  amenities: string[];
  bed_label: string;
  availability_label?: string;
}

export type BookingStepId = 'dates' | 'room' | 'guest' | 'confirmation';

export interface BookingStepState {
  current_step: BookingStepId;
  check_in?: string;
  check_out?: string;
  room_name?: string;
  guest_count?: number;
  total?: number;
  currency?: string;
}

export interface CaptionLine {
  id: string;
  speaker: 'agent' | 'guest' | 'system';
  text: string;
  isFinal: boolean;
  createdAt: number;
}

export type ClientUiEvent =
  | { type: 'client_touch_override'; room_id: string; label: string }
  | { type: 'text_message'; text: string }
  | { type: 'ptt_state'; active: boolean }
  | { type: 'request_out_loud_confirmation'; subject: string }
  | { type: 'request_secure_checkout' };

export type ServerUiEvent =
  | { type: 'session_ready'; agent_name: string; message: string; confirmation_required: boolean }
  | { type: 'caption'; speaker: 'agent' | 'guest'; text: string; is_final?: boolean }
  | { type: 'room_card'; room: RoomCardModel }
  | { type: 'booking_stepper'; booking: BookingStepState }
  | { type: 'checkout_prompt'; amount: number; currency: string; description: string }
  | { type: 'selection_acknowledged'; room_id: string; message: string }
  | { type: 'text_acknowledged'; message: string }
  | { type: 'ptt_acknowledged'; active: boolean }
  | { type: 'confirmation_required'; subject: string; message: string }
  | { type: 'checkout_unavailable'; message: string }
  | { type: 'ui_error'; message: string };

/** Type guard for arbitrary JSON received through a browser DataChannel. */
export function parseServerUiEvent(value: unknown): ServerUiEvent | null {
  if (!isRecord(value) || typeof value.type !== 'string') return null;
  const type = value.type;
  if (
    type === 'session_ready' &&
    isString(value.agent_name) &&
    isString(value.message) &&
    typeof value.confirmation_required === 'boolean'
  ) {
    return { type, agent_name: value.agent_name, message: value.message, confirmation_required: value.confirmation_required };
  }
  if (type === 'caption' && isSpeaker(value.speaker) && isString(value.text)) {
    return { type, speaker: value.speaker, text: value.text, is_final: value.is_final === true };
  }
  if (type === 'room_card' && isRoomCard(value.room)) return { type, room: value.room };
  if (type === 'booking_stepper' && isBookingState(value.booking)) return { type, booking: value.booking };
  if (type === 'checkout_prompt' && isNumber(value.amount) && isString(value.currency) && isString(value.description)) {
    return { type, amount: value.amount, currency: value.currency, description: value.description };
  }
  if (type === 'selection_acknowledged' && isString(value.room_id) && isString(value.message)) {
    return { type, room_id: value.room_id, message: value.message };
  }
  if (type === 'text_acknowledged' && isString(value.message)) return { type, message: value.message };
  if (type === 'ptt_acknowledged' && typeof value.active === 'boolean') return { type, active: value.active };
  if (type === 'confirmation_required' && isString(value.subject) && isString(value.message)) {
    return { type, subject: value.subject, message: value.message };
  }
  if ((type === 'checkout_unavailable' || type === 'ui_error') && isString(value.message)) return { type, message: value.message };
  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === 'string';
}

function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isSpeaker(value: unknown): value is 'agent' | 'guest' {
  return value === 'agent' || value === 'guest';
}

function isRoomCard(value: unknown): value is RoomCardModel {
  if (!isRecord(value)) return false;
  return (
    isString(value.id) &&
    isString(value.name) &&
    isString(value.description) &&
    isNumber(value.price_per_night) &&
    isString(value.currency) &&
    Array.isArray(value.amenities) &&
    value.amenities.every(isString) &&
    isString(value.bed_label) &&
    (value.image_url === undefined || isString(value.image_url)) &&
    (value.availability_label === undefined || isString(value.availability_label))
  );
}

function isBookingState(value: unknown): value is BookingStepState {
  if (!isRecord(value) || !isBookingStep(value.current_step)) return false;
  return (
    (value.check_in === undefined || isString(value.check_in)) &&
    (value.check_out === undefined || isString(value.check_out)) &&
    (value.room_name === undefined || isString(value.room_name)) &&
    (value.guest_count === undefined || isNumber(value.guest_count)) &&
    (value.total === undefined || isNumber(value.total)) &&
    (value.currency === undefined || isString(value.currency))
  );
}

function isBookingStep(value: unknown): value is BookingStepId {
  return value === 'dates' || value === 'room' || value === 'guest' || value === 'confirmation';
}
