import '../../i18n';
import { render, waitFor } from '@testing-library/react-native';
import { ReportScreen } from '../ReportScreen';
import { api } from '../../api/client';
import type { ShowingDetail, VerticalConfig } from '../../types';

jest.mock('../../api/client', () => ({
  api: {
    getShowing: jest.fn(),
    getVerticalConfig: jest.fn(),
    updateReport: jest.fn(),
    dismissObservation: jest.fn(),
    confirmShowing: jest.fn(),
    createShareLink: jest.fn(),
  },
}));

const mockedApi = jest.mocked(api);

const detail: ShowingDetail = {
  id: 'visit-1', status: 'draft', processingStatus: 'ready', createdAt: '2026-08-10T00:00:00Z', consentAck: true,
  property: { id: 'subject-1', displayName: '123 Main Street', address: '123 Main Street' }, contact: null,
  observations: [{
    id: 'observation-1', zoneId: 'zone-1', category: 'concern', content: 'The street is busy.',
    sourceTranscriptSegmentId: null, timestampStart: null, flags: {}, reviewStatus: 'confirmed',
  }],
  report: {
    id: 'report-1', status: 'draft', content: {
      executive_summary: 'A concise summary.',
      room_by_room: [{ zone_id: 'zone-1', zone_type: 'primary_bedroom', bullets: [{ text: 'Good light.', observation_ids: [] }] }],
      highlights: [], concerns: [], follow_ups: [],
    },
  },
};

const config: VerticalConfig = {
  zoneTaxonomy: ['primary_bedroom'], observationSchema: ['concern'],
  displayLabels: { zones: { primary_bedroom: 'Primary bedroom' }, observations: { concern: 'Buyer concern' } },
};

describe('ReportScreen vertical labels', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedApi.getShowing.mockResolvedValue(detail);
  });

  test('renders configured zone and observation labels', async () => {
    mockedApi.getVerticalConfig.mockResolvedValue(config);

    const screen = await render(<ReportScreen visitId="visit-1" onBack={() => undefined} />);

    await waitFor(() => expect(screen.getByText('Primary bedroom')).toBeTruthy());
    expect(screen.getByText('Buyer concern')).toBeTruthy();
    expect(screen.queryByText('primary_bedroom')).toBeNull();
    expect(screen.queryByText('concern')).toBeNull();
  });

  test('uses readable fallbacks when config cannot be fetched', async () => {
    mockedApi.getVerticalConfig.mockRejectedValue(new Error('offline'));
    const unknownDetail = {
      ...detail,
      observations: [{ ...detail.observations[0]!, category: 'future_category' }],
      report: { ...detail.report!, content: { ...detail.report!.content, room_by_room: [{ ...detail.report!.content.room_by_room[0]!, zone_type: 'future_zone' }] } },
    };
    mockedApi.getShowing.mockResolvedValue(unknownDetail);

    const screen = await render(<ReportScreen visitId="visit-1" onBack={() => undefined} />);

    await waitFor(() => expect(screen.getByText('Future zone')).toBeTruthy());
    expect(screen.getByText('Future category')).toBeTruthy();
    expect(screen.queryByText('future_zone')).toBeNull();
    expect(screen.queryByText('future_category')).toBeNull();
  });
});
