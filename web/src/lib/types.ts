export interface StreamEvent {
  type: 'scene_start' | 'story_text_delta' | 'diagram_ready' | 'caption_ready' | 'audio_ready' | 'scene_done' | 'final_bundle_ready';
  scene_id?: string;
  data: any;
}
