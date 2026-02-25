/**
 * Tests for DataStore module
 * Run with: npm test
 */

// Mock fetch globally
global.fetch = jest.fn();

// Load the module
const fs = require('fs');
const path = require('path');
const dataStoreCode = fs.readFileSync(path.join(__dirname, 'dataStore.js'), 'utf8');
eval(dataStoreCode);

describe('DataStore', () => {
    beforeEach(() => {
        // Reset fetch mock
        global.fetch.mockReset();
        // Clear DataStore state
        DataStore.clearAll();
    });

    describe('subscribe()', () => {
        test('should add subscriber for valid data type', () => {
            const callback = jest.fn();
            const unsubscribe = DataStore.subscribe('features', callback);

            expect(typeof unsubscribe).toBe('function');
        });

        test('should warn for unknown data type', () => {
            const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
            const callback = jest.fn();

            DataStore.subscribe('unknownType', callback);

            expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining('Unknown data type'));
            consoleSpy.mockRestore();
        });

        test('should return working unsubscribe function', () => {
            const callback = jest.fn();
            const unsubscribe = DataStore.subscribe('features', callback);

            unsubscribe();

            // Set data to trigger notify - callback should not be called
            DataStore.set('features', [{ id: 1, name: 'test' }]);
            expect(callback).not.toHaveBeenCalled();
        });

        test('should support wildcard subscriptions', () => {
            const callback = jest.fn();
            DataStore.subscribe('*', callback);

            DataStore.set('features', [{ id: 1 }]);

            expect(callback).toHaveBeenCalledWith('features', expect.any(Array), expect.any(Object));
        });
    });

    describe('get()', () => {
        test('should return null for unknown data type', () => {
            const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();

            const result = DataStore.get('unknownType');

            expect(result).toBeNull();
            expect(consoleSpy).toHaveBeenCalled();
            consoleSpy.mockRestore();
        });

        test('should return cached data', () => {
            const testData = [{ id: 1, name: 'Feature 1' }];
            DataStore.set('features', testData);

            const result = DataStore.get('features');

            expect(result).toEqual(testData);
        });

        test('should return empty array for array types initially', () => {
            const result = DataStore.get('features');

            expect(result).toEqual([]);
        });
    });

    describe('getState()', () => {
        test('should return full state object', () => {
            const state = DataStore.getState('features');

            expect(state).toHaveProperty('data');
            expect(state).toHaveProperty('loading');
            expect(state).toHaveProperty('error');
            expect(state).toHaveProperty('lastFetched');
        });

        test('should return null for unknown type', () => {
            const state = DataStore.getState('unknownType');

            expect(state).toBeNull();
        });
    });

    describe('isStale()', () => {
        test('should return true when never fetched', () => {
            const result = DataStore.isStale('features');

            expect(result).toBe(true);
        });

        test('should return false when recently fetched', () => {
            DataStore.set('features', []);

            const result = DataStore.isStale('features');

            expect(result).toBe(false);
        });
    });

    describe('fetch()', () => {
        test('should fetch data from API', async () => {
            const mockData = [{ id: 1, name: 'Feature 1' }];
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockData)
            });

            const result = await DataStore.fetch('features', { force: true });

            expect(result).toEqual(mockData);
            expect(global.fetch).toHaveBeenCalledWith(
                '/api/features',
                expect.objectContaining({
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' }
                })
            );
        });

        test('should return cached data if not stale', async () => {
            const cachedData = [{ id: 1 }];
            DataStore.set('features', cachedData);

            const result = await DataStore.fetch('features');

            expect(result).toEqual(cachedData);
            expect(global.fetch).not.toHaveBeenCalled();
        });

        test('should force refresh when force option is true', async () => {
            const cachedData = [{ id: 1 }];
            DataStore.set('features', cachedData);

            const newData = [{ id: 2 }];
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(newData)
            });

            const result = await DataStore.fetch('features', { force: true });

            expect(result).toEqual(newData);
            expect(global.fetch).toHaveBeenCalled();
        });

        test('should handle API errors', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                statusText: 'Internal Server Error'
            });

            await expect(DataStore.fetch('features', { force: true }))
                .rejects
                .toThrow('API error');
        });

        test('should handle network errors', async () => {
            global.fetch.mockRejectedValueOnce(new Error('Network error'));

            await expect(DataStore.fetch('features', { force: true }))
                .rejects
                .toThrow('Network error');
        });

        test('should normalize null response to empty array for array types', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(null)
            });

            const result = await DataStore.fetch('features', { force: true });

            expect(result).toEqual([]);
        });

        test('should handle errors data nested in response', async () => {
            const mockData = { errors: [{ id: 1, message: 'Error 1' }] };
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockData)
            });

            const result = await DataStore.fetch('errors', { force: true });

            expect(result).toEqual(mockData.errors);
        });

        test('should add query params when provided', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve([])
            });

            await DataStore.fetch('features', { force: true, params: { status: 'active' } });

            expect(global.fetch).toHaveBeenCalledWith(
                '/api/features?status=active',
                expect.any(Object)
            );
        });

        test('should return null for unknown data type', async () => {
            const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();

            const result = await DataStore.fetch('unknownType');

            expect(result).toBeNull();
            consoleSpy.mockRestore();
        });

        test('should notify subscribers after successful fetch', async () => {
            const callback = jest.fn();
            DataStore.subscribe('features', callback);

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve([{ id: 1 }])
            });

            await DataStore.fetch('features', { force: true });

            expect(callback).toHaveBeenCalled();
        });
    });

    describe('set()', () => {
        test('should set data and notify subscribers', () => {
            const callback = jest.fn();
            DataStore.subscribe('features', callback);

            const data = [{ id: 1, name: 'Test' }];
            DataStore.set('features', data);

            expect(DataStore.get('features')).toEqual(data);
            expect(callback).toHaveBeenCalledWith(data, expect.any(Object));
        });

        test('should warn for unknown data type', () => {
            const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();

            DataStore.set('unknownType', []);

            expect(consoleSpy).toHaveBeenCalled();
            consoleSpy.mockRestore();
        });
    });

    describe('upsertItem()', () => {
        test('should add new item if not exists', () => {
            DataStore.set('features', [{ id: 1, name: 'First' }]);

            DataStore.upsertItem('features', { id: 2, name: 'Second' });

            expect(DataStore.get('features')).toHaveLength(2);
            expect(DataStore.get('features')[1]).toEqual({ id: 2, name: 'Second' });
        });

        test('should update existing item', () => {
            DataStore.set('features', [{ id: 1, name: 'Original' }]);

            DataStore.upsertItem('features', { id: 1, name: 'Updated' });

            expect(DataStore.get('features')).toHaveLength(1);
            expect(DataStore.get('features')[0].name).toBe('Updated');
        });

        test('should merge properties on update', () => {
            DataStore.set('features', [{ id: 1, name: 'Test', status: 'draft' }]);

            DataStore.upsertItem('features', { id: 1, status: 'active' });

            const feature = DataStore.get('features')[0];
            expect(feature.name).toBe('Test');
            expect(feature.status).toBe('active');
        });

        test('should warn for non-array data type', () => {
            const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
            DataStore.set('stats', { total: 10 });

            DataStore.upsertItem('stats', { id: 1 });

            expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining('Cannot upsert'));
            consoleSpy.mockRestore();
        });
    });

    describe('removeItem()', () => {
        test('should remove item by id', () => {
            DataStore.set('features', [
                { id: 1, name: 'First' },
                { id: 2, name: 'Second' }
            ]);

            DataStore.removeItem('features', 1);

            expect(DataStore.get('features')).toHaveLength(1);
            expect(DataStore.get('features')[0].id).toBe(2);
        });

        test('should do nothing if item not found', () => {
            DataStore.set('features', [{ id: 1, name: 'Test' }]);

            DataStore.removeItem('features', 999);

            expect(DataStore.get('features')).toHaveLength(1);
        });

        test('should warn for non-array data type', () => {
            const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
            DataStore.set('stats', { total: 10 });

            DataStore.removeItem('stats', 1);

            expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining('Cannot remove'));
            consoleSpy.mockRestore();
        });
    });

    describe('refreshAll()', () => {
        test('should fetch all data types', async () => {
            global.fetch.mockResolvedValue({
                ok: true,
                json: () => Promise.resolve([])
            });

            const result = await DataStore.refreshAll();

            expect(result.success).toBeGreaterThan(0);
            expect(global.fetch).toHaveBeenCalled();
        });

        test('should report failures', async () => {
            global.fetch.mockRejectedValue(new Error('Network error'));
            const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();

            const result = await DataStore.refreshAll();

            expect(result.failed).toBeGreaterThan(0);
            expect(result.errors.length).toBeGreaterThan(0);
            consoleSpy.mockRestore();
        });
    });

    describe('getCounts()', () => {
        test('should return counts for all data types', () => {
            DataStore.set('features', [
                { id: 1, status: 'proposed' },
                { id: 2, status: 'in_progress' },
                { id: 3, status: 'completed' }
            ]);
            DataStore.set('bugs', [
                { id: 1, status: 'open', severity: 'critical' },
                { id: 2, status: 'resolved' }
            ]);

            const counts = DataStore.getCounts();

            expect(counts.features.total).toBe(3);
            expect(counts.features.proposed).toBe(1);
            expect(counts.features.in_progress).toBe(1);
            expect(counts.features.completed).toBe(1);
            expect(counts.bugs.total).toBe(2);
            expect(counts.bugs.open).toBe(1);
            expect(counts.bugs.critical).toBe(1);
        });

        test('should handle empty data gracefully', () => {
            const counts = DataStore.getCounts();

            expect(counts.features.total).toBe(0);
            expect(counts.bugs.total).toBe(0);
        });

        test('should handle workers data structure', () => {
            DataStore.set('workers', {
                stats: { total: 5, active: 3, idle: 1, offline: 1 }
            });

            const counts = DataStore.getCounts();

            expect(counts.workers.total).toBe(5);
            expect(counts.workers.active).toBe(3);
        });
    });

    describe('invalidate()', () => {
        test('should mark data as stale', () => {
            DataStore.set('features', []);
            expect(DataStore.isStale('features')).toBe(false);

            DataStore.invalidate('features');

            expect(DataStore.isStale('features')).toBe(true);
        });
    });

    describe('clearAll()', () => {
        test('should clear all cached data', () => {
            DataStore.set('features', [{ id: 1 }]);
            DataStore.set('bugs', [{ id: 1 }]);

            DataStore.clearAll();

            expect(DataStore.get('features')).toEqual([]);
            expect(DataStore.get('bugs')).toEqual([]);
        });
    });

    describe('error handling in subscribers', () => {
        test('should catch errors in subscriber callbacks', () => {
            const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
            const errorCallback = () => { throw new Error('Subscriber error'); };
            DataStore.subscribe('features', errorCallback);

            // Should not throw
            expect(() => {
                DataStore.set('features', [{ id: 1 }]);
            }).not.toThrow();

            expect(consoleSpy).toHaveBeenCalledWith(
                expect.stringContaining('Error in features subscriber'),
                expect.any(Error)
            );
            consoleSpy.mockRestore();
        });

        test('should catch errors in wildcard subscriber callbacks', () => {
            const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
            const errorCallback = () => { throw new Error('Wildcard error'); };
            DataStore.subscribe('*', errorCallback);

            expect(() => {
                DataStore.set('features', [{ id: 1 }]);
            }).not.toThrow();

            expect(consoleSpy).toHaveBeenCalledWith(
                expect.stringContaining('Error in wildcard subscriber'),
                expect.any(Error)
            );
            consoleSpy.mockRestore();
        });
    });
});
