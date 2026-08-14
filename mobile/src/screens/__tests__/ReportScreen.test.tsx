import '../../i18n';
import { Alert } from 'react-native';
import { render, waitFor } from '@testing-library/react-native';
import { ReportScreen } from '../ReportScreen';
import { api } from '../../api/client';
import { readShowingDetail, readVerticalConfig, writeShowingDetail } from '../../storage/cache';
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
jest.mock('../../storage/cache', () => ({
  readShowingDetail: jest.fn(async () => null),
  readVerticalConfig: jest.fn(async () => null),
  writeShowingDetail: jest.fn(async () => undefined),
  writeVerticalConfig: jest.fn(async () => undefined),
}));

const mockedApi = jest.mocked(api);
const mockedCache = {
  readShowingDetail: readShowingDetail as jest.Mock,
  readVerticalConfig: readVerticalConfig as jest.Mock,
  writeShowingDetail: writeShowingDetail as jest.Mock,
};

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
  consent: null,
};

describe('ReportScreen vertical labels', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedApi.getShowing.mockResolvedValue(detail);
    mockedCache.readShowingDetail.mockResolvedValue(null);
    mockedCache.readVerticalConfig.mockResolvedValue(null);
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

describe('ReportScreen offline behaviour', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedApi.getVerticalConfig.mockResolvedValue(config);
    mockedCache.readShowingDetail.mockResolvedValue(null);
    mockedCache.readVerticalConfig.mockResolvedValue(null);
  });

  test('renders the last synced report read-only when the fetch fails', async () => {
    mockedCache.readShowingDetail.mockResolvedValue(detail);
    mockedApi.getShowing.mockRejectedValue(new Error('offline'));

    const screen = await render(<ReportScreen visitId="visit-1" onBack={() => undefined} />);

    await waitFor(() => expect(screen.getByText('A concise summary.')).toBeTruthy());
    expect(screen.getByText(/Offline — showing the last synced copy/)).toBeTruthy();
    // Every mutation needs the server, so none of them may be offered.
    expect(screen.queryByText('Fix typo')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Delete observation' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Confirm report' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Review on desktop' })).toBeNull();
  });

  test('restores the editable report once the fetch succeeds', async () => {
    mockedCache.readShowingDetail.mockResolvedValue(detail);
    mockedApi.getShowing.mockResolvedValue(detail);

    const screen = await render(<ReportScreen visitId="visit-1" onBack={() => undefined} />);

    await waitFor(() => expect(screen.getAllByText('Fix typo').length).toBeGreaterThan(0));
    expect(screen.queryByText(/Offline — showing the last synced copy/)).toBeNull();
    expect(mockedCache.writeShowingDetail).toHaveBeenCalledWith(detail);
  });

  test('still reports an error when nothing is cached and the fetch fails', async () => {
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    mockedCache.readShowingDetail.mockResolvedValue(null);
    mockedApi.getShowing.mockRejectedValue(new Error('offline'));

    await render(<ReportScreen visitId="visit-1" onBack={() => undefined} />);

    await waitFor(() => expect(alert).toHaveBeenCalledWith('Something went wrong.'));
    alert.mockRestore();
  });
});
