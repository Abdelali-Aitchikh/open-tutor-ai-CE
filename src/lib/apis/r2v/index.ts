import { TUTOR_API_BASE_URL } from '$lib/constants';

export type R2VRequestPayload = {
	question: string;
	chat_id?: string;
	language?: string;
	duration_sec?: number;
	model_id?: string;
};

export type R2VStreamEvent = {
	event: string;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	data: any;
};

export const startR2VStream = async (
	token: string,
	payload: R2VRequestPayload
): Promise<Response> => {
	console.log('[R2V API] startR2VStream called', {
		hasToken: !!token,
		chat_id: payload.chat_id,
		language: payload.language,
		duration_sec: payload.duration_sec,
		questionPreview: payload.question?.slice(0, 120)
	});

	try {
		const response = await fetch(`${TUTOR_API_BASE_URL}/r2v/generate`, {
			method: 'POST',
			headers: {
				Accept: 'text/event-stream',
				'Content-Type': 'application/json',
				...(token && { authorization: `Bearer ${token}` })
			},
			body: JSON.stringify(payload)
		});

		console.log('[R2V API] startR2VStream response metadata', {
			ok: response.ok,
			status: response.status,
			statusText: response.statusText,
			hasBody: !!response.body
		});

		if (!response.ok) {
			let detail = '';
			try {
				detail = await response.text();
			} catch (error) {
				console.error('[R2V API] Failed to read non-OK response body', error);
			}
			throw new Error(`R2V HTTP error ${response.status}: ${detail || response.statusText}`);
		}

		if (!response.body) {
			throw new Error('R2V stream response does not contain a readable body.');
		}

		return response;
	} catch (error) {
		console.error('[R2V API] startR2VStream failed', error);
		throw error;
	}
};

export async function* readR2VStream(
	response: Response
): AsyncGenerator<R2VStreamEvent> {
	console.log('[R2V API] readR2VStream begin');

	if (!response.body) {
		console.error('[R2V API] readR2VStream missing body');
		throw new Error('Response body is not readable for SSE stream.');
	}

	const reader = response.body.getReader();
	const decoder = new TextDecoder('utf-8');
	let buffer = '';

	try {
		while (true) {
			const { done, value } = await reader.read();
			console.log('[R2V API] reader.read()', {
				done,
				chunkBytes: value?.length ?? 0
			});

			if (done) {
				break;
			}

			if (!value) {
				continue;
			}

			buffer += decoder.decode(value, { stream: true }).replaceAll('\r\n', '\n');

			let separatorIndex = buffer.indexOf('\n\n');
			while (separatorIndex !== -1) {
				const rawBlock = buffer.slice(0, separatorIndex).trim();
				buffer = buffer.slice(separatorIndex + 2);

				if (rawBlock.length > 0) {
					const parsed = parseSSEBlock(rawBlock);
					if (parsed !== null) {
						console.log('[R2V API] parsed SSE event', parsed);
						yield parsed;
					}
				}

				separatorIndex = buffer.indexOf('\n\n');
			}
		}

		if (buffer.trim().length > 0) {
			const parsed = parseSSEBlock(buffer.trim());
			if (parsed !== null) {
				console.log('[R2V API] parsed trailing SSE event', parsed);
				yield parsed;
			}
		}
	} catch (error) {
		console.error('[R2V API] readR2VStream failed while reading stream', error);
		throw error;
	} finally {
		try {
			reader.releaseLock();
			console.log('[R2V API] reader lock released');
		} catch (releaseError) {
			console.error('[R2V API] failed to release reader lock', releaseError);
		}
	}
}

const parseSSEBlock = (rawBlock: string): R2VStreamEvent | null => {
	try {
		const lines = rawBlock.split('\n');
		let event = 'message';
		const dataLines: string[] = [];

		for (const line of lines) {
			if (line.startsWith('event:')) {
				event = line.slice(6).trim();
				continue;
			}
			if (line.startsWith('data:')) {
				dataLines.push(line.slice(5).trimStart());
			}
		}

		const rawData = dataLines.join('\n');
		if (!rawData) {
			console.log('[R2V API] empty SSE data payload, skipping block');
			return null;
		}

		if (rawData === '[DONE]') {
			return { event: 'done', data: '[DONE]' };
		}

		try {
			const data = JSON.parse(rawData);
			return { event, data };
		} catch (jsonError) {
			console.error('[R2V API] failed to parse SSE data JSON', {
				rawData,
				jsonError
			});
			return { event, data: { raw: rawData } };
		}
	} catch (error) {
		console.error('[R2V API] parseSSEBlock failed', { rawBlock, error });
		return null;
	}
};
